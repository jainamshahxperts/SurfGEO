import os
import json
import logging
from typing import List, Dict, Optional
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
class SEOVisibilityAgentConfig:
    GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY")
    model_name: str = "gemini-2.0-flash"
    temperature: float = 0.7

# ------------------------- STATE -------------------------
class SEOVisibilityState(BaseModel):
    website_content: str
    seo_keywords: List[str]
    visibility_report: Optional[Dict] = None

# ------------------------- AGENT -------------------------
class SEOVisibilityAgent:
    def __init__(self, config: SEOVisibilityAgentConfig):
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

    def generate_visibility_report(self, state: SEOVisibilityState) -> SEOVisibilityState:
        prompt = f"""
        You're an advanced SEO and AI visibility auditor.

        INPUT WEBSITE CONTENT:
        {state.website_content}

        TARGET SEO KEYWORDS:
        {json.dumps(state.seo_keywords, indent=2)}

        TASK:
        - Determine which prompts (questions or queries) on platforms like ChatGPT, Perplexity, Gemini the website would likely show up for.
        - Identify prompts the website *should* show up for (based on keywords) but doesn't.
        - For each missing prompt, suggest one reason and a content improvement idea.
        - Identify competitors that appear in these missing slots.
        - Suggest 5-10 low-competition opportunity prompts based on niche trends.

        Return final answer as structured JSON:
        {{
        "summary": {{
            "keywords_analyzed": ..., 
            "prompts_found": ..., 
            "missing_prompts": ..., 
            "competitors_detected": ..., 
            "opportunities": ...
        }},
        "ranking_prompts": [
            {{"prompt": ..., "position": ..., "source": ..., "matched_keyword": ...}}
        ],
        "missing_prompts": [
            {{"prompt": ..., "reason": ..., "suggested_content_improvement": ...}}
        ],
        "competitor_insights": [
            {{"keyword": ..., "prompt": ..., "competitor": ..., "rank_position": ...}}
        ],
        "opportunity_prompts": [
            {{"prompt": ..., "estimated_competition": ..., "suggested_action": ...}}
        ]
        }}
        """

        response = self._call_llm(prompt)
        try:
            json_match = re.search(r"{.*}", response, re.DOTALL)
            if not json_match:
                raise ValueError("No JSON block found in LLM response.")

            raw_json = json_match.group(0)
            raw_json = re.sub(r",\s*([}\]])", r"\\1", raw_json)  # remove trailing commas
            raw_json = re.sub(r"{\s*}", "", raw_json)             # remove empty objects

            state.visibility_report = json.loads(raw_json)

        except Exception as e:
            logger.error(f"Error parsing JSON from LLM: {e}\nResponse was:\n{response}")
            state.visibility_report = {}

        return state

# ------------------------- USAGE EXAMPLE -------------------------
def run_seo_visibility_agent(website_content: str, seo_keywords: List[str]):
    config = SEOVisibilityAgentConfig()
    agent = SEOVisibilityAgent(config)
    state = SEOVisibilityState(website_content=website_content, seo_keywords=seo_keywords)
    result_state = agent.generate_visibility_report(state)
    with open("opportunity.json","w") as f:
        json.dump(result_state.visibility_report, f, indent=4)
    print("\n===== SEO VISIBILITY REPORT =====\n")
    print(json.dumps(result_state.visibility_report, indent=2, ensure_ascii=False))
    return result_state

# Example usage (remove or comment this block if importing elsewhere)
if __name__ == "__main__":
    content = """
At GrowthKart, we specialize in driving e-commerce growth through full-funnel digital marketing.

Whether you're a D2C startup or an established brand, our team helps you increase revenue through SEO, performance marketing, and customer retention strategies.

🚀 What We Offer:
- Google Ads & Meta Ads Management optimized for ROAS
- Conversion-optimized landing pages for your top-selling SKUs
- SEO audits, product page optimization, and backlink campaigns
- Klaviyo, WhatsApp, and SMS flows to boost LTV and reduce churn

💼 Who We Serve:
- D2C brands scaling from 5 to 50 lakh/month revenue
- Beauty, Apparel, Home, and Health categories
- Shopify & WooCommerce stores looking for plug-and-play growth teams

📈 Client Wins:
- ₹4.2 CR in Q1 revenue for a skincare brand with 6.1x ROAS
- 3x organic traffic increase for a sustainable fashion brand
- ₹22 Lakh revenue from email flows in 45 days

Join 75+ e-commerce brands that trust GrowthKart as their performance partner.
"""
    keywords = ["affordable e-commerce marketing solutions",
    "e-commerce SEO audit checklist",
    "affordable e-commerce automation tools",
    "e-commerce keyword research tools",
    "e-commerce SEO for beginners",
    "e-commerce website design best practices",
    "e-commerce digital marketing campaign challenges",
    "e-commerce product page optimization",
    "e-commerce marketing automation best practices",
    "international e-commerce digital marketing strategies",
    "customer journey mapping e-commerce digital marketing",
    "e-commerce platforms digital marketing impact",
    "handle customer reviews e-commerce",
    "why is mobile optimization important for e-commerce",
    "video marketing e-commerce product pages",
    "e-commerce digital marketing budget",
    "what is e-commerce conversion rate optimization",
    "product photography e-commerce best practices",
    "e-commerce digital marketing legal considerations",
    "segment e-commerce email list",
    "e-commerce digital marketing KPIs",
    "e-commerce digital marketing mistakes to avoid",
    "drive repeat purchases e-commerce customers",
    "reduce e-commerce cart abandonment",
    "data analytics e-commerce digital marketing",
    "effective e-commerce digital marketing strategies",
    "build strong brand identity e-commerce",
    "latest e-commerce digital marketing trends",
    "track e-commerce digital marketing ROI",
    "personalize customer experience e-commerce website",
    "improve e-commerce website SEO ranking",
    "content marketing drive traffic e-commerce",
    "optimize e-commerce website for mobile",
    "influencer marketing for e-commerce products",
    "retargeting e-commerce potential customers",
    "best social media marketing for e-commerce sales",
    "improve e-commerce website conversion rate",
    "best e-commerce SEO tactics 2024",
    "best email marketing strategies for e-commerce",
    "top e-commerce marketing strategies",
    "best e-commerce digital marketing tools",
    "how to improve e-commerce SEO organically",
    "paid advertising for e-commerce (Google Ads, Facebook Ads)",
    "best e-commerce platform for SEO",
    "e-commerce email marketing automation",
    "increase e-commerce sales organic traffic",
    "e-commerce social media advertising tips",
    "best e-commerce customer retention strategies",
    "e-commerce digital marketing agency",
    "ecommerce seo consultant"]

    run_seo_visibility_agent(content, keywords)
