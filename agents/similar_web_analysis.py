import asyncio
import json
import logging
import os
import re
from typing import Dict, Any, Optional, TYPE_CHECKING
from pydantic import BaseModel
from dotenv import load_dotenv
from playwright.async_api import async_playwright

if TYPE_CHECKING:
    from .schemas import ResearchState

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

def reduce_error(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    return existing or new

def reduce_similar_web_data(existing: Optional[dict], new: Optional[dict]) -> Optional[dict]:
    return existing or new

class SimilarWebTrafficAgent:
    def __init__(self):
        self.api_url = "https://data.similarweb.com/api/v1/data?domain={domain}"
        logger.info("Initialized SimilarWebTrafficAgent")

    async def _playwright_fetch(self, domain: str) -> Dict[str, Any]:
        url = self.api_url.format(domain=domain)
        try:
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
                page = await context.new_page()
                await page.goto(url, wait_until="domcontentloaded")

                json_text = await page.evaluate("() => document.body.innerText")

                try:
                    data = json.loads(json_text)
                    logger.info(f"Successfully fetched SimilarWeb data for {domain} via Playwright")
                    return {
                        "success": True,
                        "site": {
                            "site_name": data.get("SiteName", ""),
                            "title": data.get("Title", ""),
                            "description": data.get("Description", "")
                        },
                        "engagement": data.get("Engagements", {}),
                        "traffic_sources": data.get("TrafficSources", {}),
                        "top_country_shares": data.get("TopCountryShares", []),
                        "estimated_monthly_visits": data.get("EstimatedMonthlyVisits", {}),
                        "top_keywords": data.get("TopKeywords", [])
                    }
                except json.JSONDecodeError as e:
                    return {"success": False, "error": f"JSON parse failed: {e}"}
        except Exception as e:
            return {"success": False, "error": f"Playwright error: {str(e)}"}

    def _save_analysis_results(self, analysis_data: Dict[str, Any], filename: str = "output/similar_web.json") -> None:
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(analysis_data, f, indent=4)
            logger.info(f"SimilarWeb analysis results saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving results: {e}")

    def analyze(self, state: "ResearchState") -> "ResearchState":
        logger.info("Starting SimilarWeb traffic analysis...")
        print("Starting SimilarWeb traffic analysis...")

        domain = state.get("domain", state.get("company_name", "")).strip().lower()
        if not domain:
            error_msg = "No domain or company_name provided."
            logger.error(error_msg)
            state["error"] = reduce_error(state.get("error"), error_msg)
            return state

        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9](?:\.[a-zA-Z]{2,})+$', domain):
            error_msg = f"Invalid domain format: {domain}"
            logger.error(error_msg)
            state["error"] = reduce_error(state.get("error"), error_msg)
            return state

        try:
            similarweb_data = asyncio.run(self._playwright_fetch(domain))
            if not similarweb_data.get("success"):
                error_msg = similarweb_data.get("error", "Unknown error")
                logger.error(f"Error: {error_msg}")
                state["error"] = reduce_error(state.get("error"), error_msg)
                return state

            self._save_analysis_results(similarweb_data)
            state["similar_web_data"] = reduce_similar_web_data(state.get("similar_web_data"), similarweb_data)
            logger.info("SimilarWeb traffic analysis completed successfully")
            print("SimilarWeb traffic analysis completed successfully")

            return state

        except Exception as e:
            error_msg = f"Final error in SimilarWeb analysis: {e}"
            logger.error(error_msg)
            state["error"] = reduce_error(state.get("error"), error_msg)
            return state
