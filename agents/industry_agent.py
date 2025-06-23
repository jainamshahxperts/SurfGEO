import os
import json
import logging
from dotenv import load_dotenv
import google.generativeai as genai
from collections import defaultdict
from typing import List, Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class IndustryAgent:
    def __init__(self):
        """Initialize the IndustryAgent with required configurations."""
        self.api_key = os.getenv("GOOGLE_API_KEY")
        if not self.api_key:
            raise ValueError("GOOGLE_API_KEY not found in environment variables")
        
        genai.configure(api_key=self.api_key)
        self.model = genai.GenerativeModel('gemini-2.0-flash')
    
    def analyze_industry_mentions(self, prompt_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Analyze industry mentions from prompt data.
        
        Args:
            prompt_data: List of prompt analysis data
            
        Returns:
            Dictionary containing industry analysis results
        """
        mention_counts = defaultdict(int)

        for entry in prompt_data:
            company = entry.get("top_competitor")
            mentions = entry.get("company_mentions", 0)
            if company:
                mention_counts[company] += mentions

        # Total mentions
        total_mentions = sum(mention_counts.values())

        # Build output structure
        ranking_list = []
        for name, count in sorted(mention_counts.items(), key=lambda x: x[1], reverse=True):
            percent = (count / total_mentions) * 100 if total_mentions > 0 else 0
            ranking_list.append({
                "name": name,
                "mention_count": count,
                "percentage": round(percent, 2),
                "rank": None,  # Will be added later
            })

        # Assign ranks
        for i, item in enumerate(ranking_list, 1):
            item["rank"] = i

        return {
            "shareholding_distribution": ranking_list,
            "total_mentions": total_mentions,
            "unique_companies": len(mention_counts)
        }
    
    def run_industry_analysis(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """
        Run industry analysis on the current state.
        
        Args:
            state: Current research state
            
        Returns:
            Updated research state with industry analysis
        """
        try:
            prompt_data = state["prompt_report"]["analysis"]
            
            if not prompt_data:
                logger.warning("No prompt data found for industry analysis")
                state["industry_analysis"] = {"error": "No prompt data available for analysis"}
                return state
            
            # Perform industry analysis
            industry_analysis = self.analyze_industry_mentions(prompt_data)
            
            # Update state with results
            state["industry_analysis"] = industry_analysis
            
            # Save results to output file (optional)
            os.makedirs("output", exist_ok=True)
            output_path = os.path.join("output", "ranking_analysis_output.json")
            with open(output_path, "w") as f:
                json.dump(industry_analysis, f, indent=2)

            print("✅ Analysis complete. See `ranking_analysis_output.json`.")

            state["ranking_analysis_output"] = industry_analysis
            return state
        except Exception as e:
            logger.error("Error running industry analysis: %s", str(e))
            state["error"] = f"Industry analysis error: {str(e)}"
            return state

def run_industry_analysis(state: Dict[str, Any]) -> Dict[str, Any]:
    agent = IndustryAgent()
    return agent.run_industry_analysis(state)
