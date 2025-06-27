import os
import json
import requests
from fastapi import FastAPI, Query
from dotenv import load_dotenv
from bs4 import BeautifulSoup
from json import JSONDecodeError
import google.generativeai as genai
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load environment variables
load_dotenv()
SERPAPI_KEY = os.getenv("SERPAPI_API_KEY")
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
genai.configure(api_key=GOOGLE_API_KEY)

gemini = genai.GenerativeModel("gemini-1.5-flash")
app = FastAPI(title="SEO Keyword Analyzer API")

# 1. Google Search with SerpAPI
def search_google(domain, num_results=10):
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
    return [r.get("link") for r in results if "link" in r][:num_results]

# 2. Scrape a webpage
def scrape(url):
    try:
        r = requests.get(url, timeout=10)
        soup = BeautifulSoup(r.text, "html.parser")
        for tag in soup(["script", "style", "header", "footer", "nav"]):
            tag.decompose()
        return soup.get_text(separator=" ", strip=True)[:8000]
    except Exception as e:
        print(f"❌ Error scraping {url}: {e}")
        return ""

# 3. Scrape all in parallel
def scrape_all(urls):
    texts = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(scrape, url): url for url in urls}
        for future in as_completed(futures):
            url = futures[future]
            try:
                texts.append(future.result())
                print(f"✅ Scraped: {url}")
            except Exception as e:
                print(f"❌ Failed: {url} — {e}")
    return "\n".join(texts)

# 4. Analyze keywords using Gemini
def analyze_keywords(text: str):
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
        return json.loads(output)
    except JSONDecodeError as e:
        print("❌ JSON decode error:", e)
        return []
    except Exception as e:
        print("❌ Gemini output error:", e)
        return []