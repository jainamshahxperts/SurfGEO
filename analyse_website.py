import os
import json
import requests
import logging
from fastapi import FastAPI, Query
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from json import JSONDecodeError
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor, as_completed

# === Configure Logging ===
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger(__name__)

# === Load environment variables ===
load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")

if not SERPAPI_KEY or not GOOGLE_API_KEY:
    logger.error("Missing API keys. Check your .env file.")

# === Configure Gemini ===
genai.configure(api_key=GOOGLE_API_KEY)
gemini = genai.GenerativeModel("gemini-2.0-flash")

# === Initialize FastAPI ===
app = FastAPI(title="SEO Keyword Analyzer API")

# === 1. Google Search with SerpAPI ===
def search_google(domain, num_results=10):
    logger.info(f"🔍 Searching Google for site:{domain}")
    try:
        query = f"site:{domain}"
        url = "https://serpapi.com/search"
        params = {
            "engine": "google",
            "q": query,
            "api_key": SERPAPI_KEY,
            "num": num_results
        }
        res = requests.get(url, params=params)
        results = res.json().get("organic_results", [])
        links = [r.get("link") for r in results if "link" in r][:num_results]
        logger.info(f"✅ Found {len(links)} result(s)")
        return links
    except Exception as e:
        logger.error(f"❌ Error during Google search: {e}")
        return []

# === 2. Scrape a Webpage ===
def scrape(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "header", "footer", "nav"]):
            tag.decompose()
        logger.info(f"✅ Scraped content from {url}")
        return soup.get_text(separator=" ", strip=True)[:8000]
    except Exception as e:
        logger.warning(f"❌ Error scraping {url}: {e}")
        return ""

# === 3. Scrape All in Parallel ===
def scrape_all(urls):
    texts = []
    logger.info("🚀 Starting parallel scraping...")
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(scrape, url): url for url in urls}
        for future in as_completed(futures):
            url = futures[future]
            try:
                texts.append(future.result())
            except Exception as e:
                logger.warning(f"❌ Failed: {url} — {e}")
    logger.info(f"🧹 Scraping completed. Total pages scraped: {len(texts)}")
    return "\n".join(texts)

# === 4. Analyze Keywords using Gemini ===
def analyze_keywords(text: str):
    logger.info("🧠 Analyzing keywords using Gemini...")
    prompt = f"""
You are a keyword analysis expert.

From the website content below, extract 5 important SEO keywords or phrases (Not based on frequency).

⚠️ Your ratings **must follow this exact distribution**:
- 2 keywords rated as "Poor"
- 2 keywords rated as "Average"
- 1 keyword rated as "Excellent"

Base your ratings on:
- Frequency of use
- SEO relevance
- Originality
- Search competitiveness

🎯 Output format (valid JSON only):

[
  {{ "keyword": "keyword1", "rating": "Poor" }},
  {{ "keyword": "keyword2", "rating": "Poor" }},
  {{ "keyword": "keyword3", "rating": "Average" }},
  {{ "keyword": "keyword4", "rating": "Average" }},
  {{ "keyword": "keyword5", "rating": "Excellent" }}
]

Do not include any explanation or markdown. Just return pure JSON.

Text:
\"\"\"{text}\"\"\"
"""
    try:
        response = gemini.generate_content(prompt)
        output = response.text.strip()
        if output.startswith("```json"):
            output = output.replace("```json", "").replace("```", "").strip()
        keywords = json.loads(output)
        logger.info("✅ Gemini keyword analysis complete.")
        return keywords
    except JSONDecodeError as e:
        logger.error(f"❌ JSON decode error: {e}")
        return []
    except Exception as e:
        logger.error(f"❌ Gemini output error: {e}")
        return []