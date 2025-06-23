import json
import os
import google.generativeai as genai
from dotenv import load_dotenv
from .schemas import ResearchState
import logging

logger = logging.getLogger(__name__)

load_dotenv()


class CompatibilityAgent:
    def __init__(self, model_name="gemini-2.0-flash"):
        load_dotenv()
        genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))
        self.model = genai.GenerativeModel(model_name)

    def score_pages_in_json(self, state: ResearchState) -> ResearchState:
        logger.info("Starting compatibility analysis...")
        site_pages = state.get('website_content_individual')
        if not site_pages:
            logger.warning("No website content found for compatibility analysis.")
            return state

        # Ensure site_pages is a list of dictionaries
        if isinstance(site_pages, dict):
            site_pages = list(site_pages.values())
        elif not isinstance(site_pages, list):
            logger.error(f"Unexpected type for website_content_individual: {type(site_pages)}")
            state['error'] = "Invalid website_content_individual format"
            return state

        # Filter out pages that are None or do not have a 'url' key
        site_pages = [page for page in site_pages if page and 'url' in page]

        if not site_pages:
            logger.warning("No valid pages found in website_content_individual for compatibility analysis.")
            return state

        # Build a single combined string with URL labels
        full_site_content = ""
        # Build a single combined string with URL labels
        full_site_content = ""
        for page in site_pages:
            page_block = f"""[URL: {page["url"]}]
{' '.join(page["titles"]["h1"])}
{' '.join(page["titles"]["h2"])}
{' '.join(page["titles"]["h3"])}
{' '.join(page["paragraphs"])}
{' '.join(page["lists"]["bullet_points"])}
{' '.join(page["lists"]["numbered_lists"])}

"""
            full_site_content += page_block

        prompt = f"""
You are an expert in content analysis and generative engine optimization (GEO).

Evaluate the following website content *as a whole*. Do not score each page individually. Instead, assess the site's overall structure, content quality, keyword coverage, and metadata readiness. 

Then, do three things:
1. Return ratings for the following fields as one of: "Poor", "Average", or "Excellent", with a one-line comment for each.
2. Calculate the overall GEO Compatibility Percentage (0–100).
3. Suggest all new possible "opportunity pages" that would improve coverage, depth, or topical authority. Give maximum relevant suggestions.
4. Identify all underperforming URLs (with reasons). Return maximum relevant entries.
5. Be accurate in rating

### Full Website Content:
{full_site_content}

### Rating Criteria:

1. Content: Clarity, coherence, value across site  
2. Structure: Use of headings, hierarchy, layout consistency  
3. Keywords: Presence and spread of relevant search terms  
4. Entity Coverage: Named entities, topical concepts  
5. Embedding Richness: Semantic density and representation potential  
6. Anchor Usage: Internal linking, external linking, anchor text  
7. Metadata Readiness: Page titles, meta descriptions, alt tags

### Return JSON like:

{{
  "Scores": {{
    "content": {{ "rating": "Average", "comment": "..." }},
    "structure": {{ "rating": "Poor", "comment": "..." }},
    "keywords": {{ "rating": "Excellent", "comment": "..." }},
    "entity_coverage": {{ "rating": "Average", "comment": "..." }},
    "embedding_richness": {{ "rating": "Poor", "comment": "..." }},
    "anchor_usage": {{ "rating": "Average", "comment": "..." }},
    "metadata_readiness": {{ "rating": "Excellent", "comment": "..." }}
  }},
  "geo_compatibility_percent": ...,
  "opportunity_pages": [
    "Create a page on ...",
    "Add FAQ on ..."
  ],
  "underperforming_pages": [
    {{ "url": "https://...", "issue": "Weak metadata" }}
  ]
}}
"""

        generation_config = {
            "response_mime_type": "application/json",
        }
        response = self.model.generate_content(prompt, generation_config=generation_config)
        try:
            compatibility_report = json.loads(response.text)
            state['compatibility_report'] = compatibility_report
            logger.info("Compatibility analysis completed successfully.")
            return state
        except json.JSONDecodeError as e:
            logger.error(f"❌ JSON Decode Error in compatibility_agent: {e}")
            logger.error(f"🧾 Raw response: {response.text}")
            state['error'] = f"JSON decoding error in compatibility_agent: {e}"
            return state
        except Exception as e:
            logger.error(f"An unexpected error occurred in compatibility_agent: {e}")
            state['error'] = f"Unexpected error in compatibility_agent: {e}"
            return state
