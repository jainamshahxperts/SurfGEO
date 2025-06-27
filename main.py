from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Dict, Any
from controller import run_workflow  # Import your LangGraph-based controller logic
from analyse_website import search_google, scrape_all, analyze_keywords

app = FastAPI(
    title="AI Research Workflow API",
    description="Trigger full research analysis using autonomous agents.",
    version="1.0.0"
)

# 👇 Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # 🔐 For production, replace "*" with specific domain(s)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class ResearchRequest(BaseModel):
    company_name: str


@app.post("/run", summary="Run full AI research workflow", response_model=Dict[str, Any])
async def run_research(request: ResearchRequest):
    try:
        result = await run_workflow(company_name=request.company_name)

        if result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow failed: {str(e)}")

@app.get("/analyze")
def analyze(domain: str = Query(..., description="Website domain (e.g., example.com)")):
    print(f"🔍 Searching Google for: {domain}")
    urls = search_google(domain)
    if not urls:
        return {"error": "No pages found."}

    print("⚡ Scraping in parallel...")
    all_text = scrape_all(urls)
    if not all_text:
        return {"error": "No content could be scraped."}

    print("🧠 Sending to Gemini...")
    result = analyze_keywords(all_text)
    return {"domain": domain, "keywords": result}
