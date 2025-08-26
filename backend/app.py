import os
import re
import json
import hashlib
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any

import requests
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from cachetools import TTLCache
from nltk.sentiment import SentimentIntensityAnalyzer
from nltk import download as nltk_download, data as nltk_data


import subprocess, json
from datetime import datetime, timedelta

# Optional keyword extraction (yake); spaCy for NER if installed
try:
    import yake
    _HAS_YAKE = True
except Exception:
    _HAS_YAKE = False

try:
    import spacy
    _NLP = spacy.load("en_core_web_sm")
    _HAS_SPACY = True
except Exception:
    _HAS_SPACY = False
    _NLP = None

# Ensure VADER lexicon is available
try:
    nltk_data.find("sentiment/vader_lexicon.zip")
except LookupError:
    nltk_download("vader_lexicon")

sia = SentimentIntensityAnalyzer()

app = FastAPI(title="Social OSINT Keyword & Sentiment API", version="0.1.0")

# Allow frontend access
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Cache: keep last 128 requests for 10 minutes
cache = TTLCache(maxsize=128, ttl=600)


# ---------- Models ----------
class ScrapeRequest(BaseModel):
    keyword: str
    platform: str  # 'reddit' | 'news' | 'twitter'
    timeframe_days: int = 7


class AnalyzeRequest(BaseModel):
    texts: List[str]


# ---------- Helpers ----------
def _cache_key(prefix: str, payload: Dict[str, Any]) -> str:
    return hashlib.sha256((prefix + json.dumps(payload, sort_keys=True)).encode()).hexdigest()

def _utc_now() -> datetime:
    return datetime.now(timezone.utc)

def clamp(v, lo, hi):
    return max(lo, min(hi, v))


# ---------- Scrapers ----------
def scrape_reddit(keyword: str, days: int):
    url = "https://www.reddit.com/search.json"
    headers = {"User-Agent": "osint-scraper-bot"}
    params = {"q": keyword, "sort": "new", "limit": 100}
    r = requests.get(url, headers=headers, params=params, timeout=20)
    if r.status_code != 200:
        raise HTTPException(status_code=502, detail="Reddit fetch failed")

    data = r.json()
    items, now = [], _utc_now()
    cutoff = now - timedelta(days=days)
    for child in data.get("data", {}).get("children", []):
        d = child.get("data", {})
        created = datetime.fromtimestamp(d.get("created_utc", 0), tz=timezone.utc)
        if created < cutoff:
            continue
        text = f"{d.get('title','')} {d.get('selftext','')}".strip()
        if not text:
            continue
        items.append({
            "id": d.get("id"),
            "platform": "reddit",
            "author": d.get("author"),
            "created_utc": int(created.timestamp()),
            "permalink": f"https://reddit.com{d.get('permalink','')}",
            "text": text
        })
    return items


def scrape_news(keyword: str, days: int):
    import feedparser
    feed_url = f"https://news.google.com/rss/search?q={requests.utils.quote(keyword)}&hl=en-US&gl=US&ceid=US:en"
    d = feedparser.parse(feed_url)
    items, now = [], _utc_now()
    cutoff = now - timedelta(days=days)
    for e in d.entries[:50]:
        published = now
        if hasattr(e, "published_parsed") and e.published_parsed:
            published = datetime(*e.published_parsed[:6], tzinfo=timezone.utc)
        if published < cutoff:
            continue
        text = f"{getattr(e, 'title', '')} {getattr(e, 'summary', '')}".strip()
        items.append({
            "id": hashlib.md5((e.link or text).encode()).hexdigest(),
            "platform": "news",
            "created_utc": int(published.timestamp()),
            "permalink": e.link,
            "text": text
        })
    return items



def scrape_twitter(keyword: str, days: int, use_snscrape: bool):
    if not use_snscrape:
        return []
    try:
        since = (datetime.utcnow() - timedelta(days=days)).date().isoformat()
        query = f'{keyword} since:{since} lang:en'
        cmd = ["snscrape", "--jsonl", "twitter-search", query]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)

        items = []
        for line in result.stdout.splitlines():
            tweet = json.loads(line)
            items.append({
                "id": tweet["id"],
                "platform": "twitter",
                "author": tweet["user"]["username"],
                "created_utc": int(datetime.fromisoformat(tweet["date"].replace("Z", "+00:00")).timestamp()),
                "permalink": tweet["url"],
                "text": tweet["content"]
            })
            if len(items) >= 100:
                break
        return items
    except Exception as e:
        print("❌ Twitter scrape error:", e)
        return []




def extract_hashtags(texts):
    tags = []
    for t in texts:
        tags.extend(re.findall(r"#\w+", t))
    return tags


def extract_keywords(texts):
    full = " ".join(texts)
    if _HAS_YAKE:
        kw_extractor = yake.KeywordExtractor(lan="en", n=1, top=20)
        kws = kw_extractor.extract_keywords(full)
        return [k for k, _ in sorted(kws, key=lambda x: x[1])]
    from collections import Counter
    words = re.findall(r"[A-Za-z]{3,}", full.lower())
    return [w for w, _ in Counter(words).most_common(20)]


def named_entities(texts):
    if not _HAS_SPACY or not _NLP:
        return []
    doc = _NLP(" ".join(texts))
    return list({e.text for e in doc.ents if e.label_ in {"ORG","PRODUCT","PERSON","GPE","EVENT"}})


def sentiment_scores(texts):
    counts = {"positive":0,"neutral":0,"negative":0}
    for t in texts:
        score = sia.polarity_scores(t)["compound"]
        if score >= 0.05: counts["positive"]+=1
        elif score <= -0.05: counts["negative"]+=1
        else: counts["neutral"]+=1
    return counts


# ---------- Routes ----------
@app.get("/health")
def health():
    return {"ok": True, "time": _utc_now().isoformat()}


@app.post("/scrape")
def scrape(req: ScrapeRequest):
    key = _cache_key("scrape", req.dict())
    if key in cache:
        return {"cached": True, "items": cache[key]}
    if req.platform == "reddit":
        items = scrape_reddit(req.keyword, clamp(req.timeframe_days,1,30))
    elif req.platform == "news":
        items = scrape_news(req.keyword, clamp(req.timeframe_days,1,30))
    else:
        items = scrape_twitter(req.keyword, clamp(req.timeframe_days,1,30), req.use_twitter_snscrape)
    cache[key] = items
    return {"cached": False, "items": items}


@app.post("/analyze")
def analyze(req: AnalyzeRequest):
    texts = [t for t in req.texts if t.strip()]
    if not texts:
        return {"keywords":[],"entities":[],"hashtags":[],"sentiment":{"positive":0,"neutral":0,"negative":0}}
    return {
        "keywords": extract_keywords(texts),
        "entities": named_entities(texts),
        "hashtags": extract_hashtags(texts),
        "sentiment": sentiment_scores(texts),
        "samples": texts[:10]
    }
