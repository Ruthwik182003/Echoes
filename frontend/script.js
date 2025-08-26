document.addEventListener("DOMContentLoaded", () => {
  const darkToggle = document.getElementById("darkToggle");
  const form = document.getElementById("searchForm");
  const statusDiv = document.getElementById("status");

  // --- Dark Mode Toggle ---
  darkToggle.addEventListener("click", () => {
    document.body.classList.toggle("dark");
    darkToggle.textContent = document.body.classList.contains("dark")
      ? "☀ Light Mode"
      : "🌙 Dark Mode";
  });

  // --- Handle Form Submission ---
  form.addEventListener("submit", async (e) => {
    e.preventDefault();

    const keyword = document.getElementById("keyword").value.trim();
    const platform = document.getElementById("platform").value;
    const days = document.getElementById("days").value;

    if (!keyword) {
      statusDiv.textContent = "⚠ Please enter a keyword!";
      return;
    }

    statusDiv.textContent = `🔎 Searching "${keyword}" on ${platform} (last ${days} days)...`;

    try {
      // Step 1: Scrape posts
      const scrapeRes = await fetch("http://127.0.0.1:8000/scrape", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          keyword,
          platform,
          timeframe_days: days,
        }),
      });
      const scrapeData = await scrapeRes.json();
      const items = scrapeData.items || [];

      if (!items.length) {
        statusDiv.textContent = "⚠ No posts found.";
        document.getElementById("keywordList").innerHTML = "<li>No keywords</li>";
        document.getElementById("hashtagList").innerHTML = "<li>No hashtags</li>";
        document.getElementById("samples").innerHTML = "<p>No posts</p>";
        return;
      }

      // Extract texts only
      const texts = items.map((i) => i.text);

      // Step 2: Analyze texts
      const analyzeRes = await fetch("http://127.0.0.1:8000/analyze", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ texts }),
      });
      const data = await analyzeRes.json();

      // --- Update Dashboard ---
      if (data.sentiment) renderSentimentChart(data.sentiment);

      if (data.keywords && data.keywords.length) {
        document.getElementById("keywordList").innerHTML =
          data.keywords.map((k) => `<li>${k}</li>`).join("");
      } else {
        document.getElementById("keywordList").innerHTML = "<li>No keywords</li>";
      }

      if (data.hashtags && data.hashtags.length) {
        document.getElementById("hashtagList").innerHTML =
          data.hashtags.map((h) => `<li>${h}</li>`).join("");
      } else {
        document.getElementById("hashtagList").innerHTML = "<li>No hashtags</li>";
      }

      if (data.samples && data.samples.length) {
        document.getElementById("samples").innerHTML =
          data.samples.map((p) => `<p>💬 ${p}</p>`).join("");
      } else {
        document.getElementById("samples").innerHTML = "<p>No posts</p>";
      }

      if (data.keywords && data.keywords.length) {
        renderWordCloud(data.keywords);
      }

      statusDiv.textContent = "✅ Results updated.";
    } catch (err) {
      console.error(err);
      statusDiv.textContent = "❌ Error fetching data.";
    }
  });

  // --- Render Sentiment Pie Chart ---
  function renderSentimentChart(sentiment) {
    const ctx = document.getElementById("sentimentChart").getContext("2d");
    if (window.sentimentChartInstance) {
      window.sentimentChartInstance.destroy();
    }
    window.sentimentChartInstance = new Chart(ctx, {
      type: "pie",
      data: {
        labels: ["Positive", "Neutral", "Negative"],
        datasets: [
          {
            data: [
              sentiment.positive || 0,
              sentiment.neutral || 0,
              sentiment.negative || 0,
            ],
            backgroundColor: ["#4caf50", "#ffc107", "#f44336"],
          },
        ],
      },
    });
  }

  // --- Render Word Cloud ---
  function renderWordCloud(words) {
  if (!words || words.length === 0) {
    document.getElementById("wordCloud").innerHTML = "No words found";
    return;
  }

  // Normalize weights so all words stay visible
  const list = words.map((w, i) => [w, words.length - i]);

  WordCloud(document.getElementById("wordCloud"), {
    list: list,
    gridSize: 10,
    weightFactor: (size) => size * 5,  // keep sizes moderate
    fontFamily: "Arial, sans-serif",
    color: () => ["#1d4ed8", "#dc2626", "#16a34a", "#9333ea"][Math.floor(Math.random() * 4)],
    rotateRatio: 0.1,
    rotationSteps: 2,
    backgroundColor: "transparent",
    shuffle: true,
    drawOutOfBound: false,
    shrinkToFit: true
  });
}
});
