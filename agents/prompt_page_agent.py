import os
import json
import logging
from typing import List, Dict, Optional,Any
from dataclasses import dataclass

import google.generativeai as genai
from dotenv import load_dotenv
from pydantic import BaseModel, Field
import re

load_dotenv()
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ------------------------- CONFIG -------------------------
@dataclass
class SEOpromptAgentConfig:
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY")
    model_name: str = "gemini-2.0-flash"
    temperature: float = 0.7

# ------------------------- STATE -------------------------
class SEOpromptState(BaseModel):
    website_content: Dict[str, Any]
    seo_keywords: List[str]
    prompt_report: Optional[Dict] = None

# ------------------------- AGENT -------------------------
class SEOpromptAgent:
    def __init__(self, config: SEOpromptAgentConfig):
        self.config = config
        genai.configure(api_key=config.GOOGLE_API_KEY)
        self.model = genai.GenerativeModel(config.model_name)

    def _call_llm(self, prompt: str) -> str:
        try:
            response = self.model.generate_content(prompt,
                generation_config=genai.types.GenerationConfig(
                    temperature=self.config.temperature
                )
            )
            return response.text.strip()
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return ""

    def generate_prompt_report(self, state: SEOpromptState,company_name) -> SEOpromptState:
        prompt = f"""
ROLE: Expert SEO & AI Visibility Analyst

INPUT DATA:
WEBSITE CONTENT:
{state.website_content}

TARGET KEYWORDS:
{json.dumps(state.seo_keywords, indent=2)}

ANALYSIS REQUIREMENTS:
Analyze each keyword for AI model visibility and traditional SEO competition. Provide quantitative assessments based on current market data and AI model response patterns.

OUTPUT FORMAT (JSON ONLY):
{{
  "analysis": [
    {{
      "keyword": "exact_keyword_phrase",
      "prompt": related prompt to keyword user search on llm
      "competition_score": [1-100 integer],
      "top_competitor": "domain.com or Brand Name (if {company_name} is first, use company name here instead of 'None')",
      "top_competitor_mentions": [integer estimate],
      "company_rank": [1-100 integer or "Not Ranked"],
      "company_mentions": [integer estimate],
      "top_model": "ChatGPT|Perplexity|Gemini|Claude|Bing|Other",
      "intent": "informational|commercial|navigational|transactional"
    }}
  ]
}}

SCORING CRITERIA:
- competition_score: Market saturation level (100 = extremely competitive)
- top_competitor_mentions: Monthly AI model citations estimate
- company_rank: Position in AI model responses (1 = most frequently mentioned)
- company_mentions: Monthly AI citations for your company
- top_model: AI model most likely to surface this keyword

CONSTRAINTS:
- Return ONLY valid JSON
- Include ALL required fields for each keyword
- Use numerical values where specified
- No explanatory text or comments
- Ensure accuracy in competitor identification
"""

        response = self._call_llm(prompt)
        try:
            json_match = re.search(r"{.*}", response, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON block found in LLM response.")

            raw_json = json_match.group(0)
            raw_json = re.sub(r",\s*([}\]])", r"\\1", raw_json)  # remove trailing commas
            raw_json = re.sub(r"{\s*}", "", raw_json)             # remove empty objects

            state.prompt_report = json.loads(raw_json)

        except Exception as e:
            logger.error(f"Error parsing JSON from LLM: {e}\nResponse was:\n{response}")
            state.prompt_report = {}

        return state

    def run_prompt_node(self, state: Dict[str, Any]) -> Dict[str, Any]:
        website_content = state.get("website_content", "")
        seo_keywords = state.get("seo_keywords", [])
        company_name = state.get("company_name", "")

        if not website_content or not seo_keywords:
            logger.error("Missing website_content or seo_keywords in state for prompt generation.")
            return state

        prompt_state = SEOpromptState(website_content=website_content, seo_keywords=seo_keywords)
        result_prompt_state = self.generate_prompt_report(prompt_state,company_name)

        state["prompt_report"] = result_prompt_state.prompt_report

        # Extract unique competitors
        unique_competitors = set()
        if result_prompt_state.prompt_report and 'analysis' in result_prompt_state.prompt_report:
            for item in result_prompt_state.prompt_report['analysis']:
                if 'top_competitor' in item:
                    unique_competitors.add(item['top_competitor'])
        
        state["unique_competitors"] = list(unique_competitors)

        # Save prompt report and competitors to files
        output_dir = "output"
        os.makedirs(output_dir, exist_ok=True)

        if result_prompt_state.prompt_report:
            with open(os.path.join(output_dir, "prompt.json"), "w", encoding="utf-8") as f:
                json.dump(result_prompt_state.prompt_report, f, indent=4)
            logger.info(f"Prompt report saved to {os.path.join(output_dir, 'prompt.json')}")
        
        competitors_data = {"unique_competitors": list(unique_competitors)}
        with open(os.path.join(output_dir, "competitors.json"), "w", encoding="utf-8") as f:
            json.dump(competitors_data, f, indent=4)
        logger.info(f"Unique competitors saved to {os.path.join(output_dir, 'competitors.json')}")

        return state