import os
import json
import logging
from dotenv import load_dotenv
import google.generativeai as genai
from typing import Dict, Any, Optional
from pydantic import BaseModel

# --------------------- ENV + LOGGER ---------------------
load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# --------------------- CONFIG ---------------------
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
if not GOOGLE_API_KEY:
    raise ValueError("Missing GOOGLE_API_KEY in .env file")

genai.configure(api_key=GOOGLE_API_KEY)

class BrandAnalyticsAgent:
    def __init__(self):
        self.model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config={
                "temperature": 0.4,
                "max_output_tokens": 2048
            }
        )

    def generate_brand_metrics(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate brand metrics based on visibility and ranking data
        
        Args:
            state: Dictionary containing company data including visibility and ranking information
            
        Returns:
            Dictionary containing generated brand metrics
        """
        company_name = state.get("company_name", "")
        visibility_data = state.get("visibility_report", {})
        ranking_data = state.get("ranking_analysis_output", {})

        prompt = f"""
You are a competitive brand intelligence analyst.

I am providing two data sources:
1. visibility.json - current visibility and trust analysis of the company: {company_name}
{json.dumps(visibility_data, indent=2)}
2. ranking_analysis.json - list of 60 top competitor prompts with their respective visibility, mentions, and rankings.
{json.dumps(ranking_data, indent=2)}

Please analyze both and infer realistic, data-informed estimates of the following metrics for the company **{company_name}**:

- brand_mention_count (integer)
- traffic_estimate (realistic e.g., "5000/month")
- visibility_score (float between 0 and 100)
- share_in_industry (string percentage e.g., "17.5%")
- brand_rank (integer, 1 being the best)

Respond only in valid JSON format like:
{{
  "brand_mention_count": 1200,
  "traffic_estimate": "5000/month",
  "visibility_score": 76.4,
  "share_in_industry": "16.3%",
  "brand_rank": ..
}}
"""

        logger.info("Generating brand metrics using Gemini...")
        try:
            response = self.model.generate_content(prompt)
            
            if not response.text:
                raise ValueError("Empty response from model")
            result = json.loads(response.text.strip("```json\n").strip("```"))
            logger.info("Successfully parsed Gemini response.")
            return result
            
        except json.JSONDecodeError as e:
            logger.error("Failed to parse JSON response: %s", response.text if 'response' in locals() else 'No response')
            raise ValueError(f"Invalid JSON response from model: {str(e)}")
            
        except Exception as e:
            logger.error("Error generating brand metrics: %s", str(e))
            raise RuntimeError(f"Failed to generate brand metrics: {str(e)}")
    
    def run_brand_analytics_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run the brand analytics node in the workflow
        
        Args:
            state: Current research state
            
        Returns:
            Updated research state with brand metrics
        """
        try:
            brand_metrics = self.generate_brand_metrics(state)
            state["brand_metrics"] = brand_metrics
            with open("output/brand_metrics.json", "w", encoding='utf-8') as f:
                json.dump(brand_metrics, f, indent=4)   
            return state
        except Exception as e:
            logger.error("Error in brand analytics node: %s", str(e))
            state["error"] = f"Brand analytics error: {str(e)}"
            return state
