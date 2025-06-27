import requests
import json
import logging
import os
import re
from typing import Dict, Any, Optional, TYPE_CHECKING
from pydantic import BaseModel
from dotenv import load_dotenv

if TYPE_CHECKING:
    from .schemas import ResearchState

# Define reduction functions (from your provided code)
def reduce_error(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Keep the existing error if it exists, otherwise use the new value."""
    return existing or new

def reduce_similar_web_data(existing: Optional[dict], new: Optional[dict]) -> Optional[dict]:
    """Keep the existing similar_web_data if it exists, otherwise use the new value."""
    return existing or new

load_dotenv()

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class SimilarWebTrafficAgent:
    def __init__(self):
        self.api_url = "https://data.similarweb.com/api/v1/data?domain={domain}"
        logger.info("Initialized SimilarWebTrafficAgent")

    def _fetch_site_data(self, domain: str) -> Dict[str, Any]:
        """
        Fetch website traffic data using requests.

        Args:
            domain: The domain to fetch data for.

        Returns:
            Dictionary containing parsed SimilarWeb data or error details.
        """
        # Validate and normalize domain
        domain = domain.lower().strip()
        if not re.match(r'^[a-zA-Z0-9][a-zA-Z0-9-]{1,61}[a-zA-Z0-9](?:\.[a-zA-Z]{2,})+$', domain):
            error_msg = f"Invalid domain format: {domain}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

        url = self.api_url.format(domain=domain)
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"
        }

        try:
            response = requests.get(url, headers=headers, timeout=10)
            if response.status_code != 200:
                error_msg = f"Failed to fetch data: HTTP {response.status_code}. Response: {response.text[:1000]}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

            try:
                data = response.json()
                logger.info(f"Successfully fetched SimilarWeb data for {domain}")
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
                error_msg = f"JSON decoding error: {str(e)}. Response: {response.text[:1000]}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}

        except Exception as e:
            error_msg = f"Error fetching data: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def _save_analysis_results(self, analysis_data: Dict[str, Any], filename: str = "output/similar_web.json") -> None:
        """
        Save the SimilarWeb analysis results to a JSON file.

        Args:
            analysis_data: The data to save.
            filename: The file path to save the data to.
        """
        try:
            os.makedirs(os.path.dirname(filename), exist_ok=True)
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(analysis_data, f, indent=4)
            logger.info(f"SimilarWeb analysis results saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving SimilarWeb analysis results: {str(e)}")

    def analyze(self, state: "ResearchState") -> "ResearchState":
        """
        Analyze the website traffic data using SimilarWeb API and update the state.

        Args:
            state: The current research state containing the company name or domain to analyze.

        Returns:
            Updated research state with SimilarWeb traffic data.
        """
        logger.info("Starting SimilarWeb traffic analysis...")
        print("Starting SimilarWeb traffic analysis...")

        # Try to get domain from state, fall back to company_name
        domain = state.get("domain", state.get("company_name", ""))
        if not domain:
            error_msg = "No domain or company_name provided for SimilarWeb analysis."
            logger.error(error_msg)
            print(f"Error: {error_msg}")
            state["error"] = reduce_error(state.get("error"), error_msg)
            return state

        try:
            # Fetch SimilarWeb data
            similarweb_data = self._fetch_site_data(domain)
            if not similarweb_data.get("success"):
                error_msg = similarweb_data.get("error", "Unknown error in SimilarWeb data fetch")
                logger.error(error_msg)
                print(f"Error: {error_msg}")
                state["error"] = reduce_error(state.get("error"), error_msg)
                return state

            # Save the results to a file
            self._save_analysis_results(similarweb_data)

            # Update the state with the SimilarWeb data
            state["similar_web_data"] = reduce_similar_web_data(state.get("similar_web_data"), similarweb_data)
            logger.info("SimilarWeb traffic analysis completed successfully")
            print("SimilarWeb traffic analysis completed successfully")

            # Log results for debugging
    
            return state

        except Exception as e:
            error_msg = f"Error in SimilarWeb traffic analysis: {str(e)}"
            logger.error(error_msg)
            print(f"Error: {error_msg}")
            state["error"] = reduce_error(state.get("error"), error_msg)
            return state