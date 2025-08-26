# Social Insights Dashboard

A web app to scrape and analyze social media & news sentiment, keywords, hashtags, and trends.

## Features
- Scrapes Reddit and Google News (Twitter optional)
- Analyzes sentiment (positive/neutral/negative)
- Extracts keywords, hashtags, and named entities
- Visualizations:
  - Sentiment pie chart
  - Word cloud
  - Keyword & hashtag lists
- Caching to avoid repeated scraping

## Tech Stack
- **Backend:** FastAPI (Python)
- **Frontend:** HTML, CSS, JavaScript, Chart.js
- **NLP:** VADER, YAKE (optional), spaCy (optional)

## Setup

### Backend
```bash
Terminal 1:
cd backend
python -m venv .venv
source .venv/bin/activate   # (Linux/Mac)
.venv\Scripts\activate      # (Windows)

pip install -r requirements.txt
uvicorn main:app --reload
```

###  Frontend
```bash
Terminal 2:
cd frontend
python -m http.server 5173 
```
