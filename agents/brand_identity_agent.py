import json
from dotenv import load_dotenv
import os
import re
import google.generativeai as genai
from typing import Dict, Any
from .schemas import BrandGuideline, ResearchState

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

def brand_identity_agent(state: ResearchState) -> ResearchState:
    """
    Analyze website content to extract brand identity information.
    
    Args:
        state: ResearchState dictionary containing website content
        
    Returns:
        Updated ResearchState with brand identity information
    """
    if not state.get('website_content'):
        state['error'] = "No website content available for brand analysis"
        return state
        
    website_content = state['website_content']

    prompt=f"""
        # Enhanced Brand Strategist AI Prompt

    ```
    You are an expert Brand Strategist AI with deep expertise in brand analysis, competitive positioning, and strategic marketing. Your task is to conduct a comprehensive analysis of a company's website content to extract precise, actionable brand intelligence.

    **ANALYSIS FRAMEWORK:**

    **1. Brand Values Analysis**
    - Identify the core principles, beliefs, and ethical foundations that drive the brand
    - Look for explicit value statements, mission declarations, and implicit values demonstrated through content tone, imagery, and messaging
    - Focus on authentic values that appear consistently across different sections of the website
    - Distinguish between aspirational values and genuinely practiced principles

    **2. Brand Goals Analysis** 
    - Extract both explicit strategic objectives and implicit goals revealed through content structure and emphasis
    - Identify short-term tactical goals (6-18 months) and long-term strategic vision (2-5+ years)
    - Look for growth ambitions, market expansion plans, customer acquisition targets, and transformation initiatives
    - Consider goals related to market position, customer experience, innovation, and social impact

    **3. Unique Selling Propositions Analysis**
    - Identify specific differentiators that create competitive advantage
    - Look for unique features, proprietary technology, exclusive processes, or distinctive approaches
    - Analyze how the brand positions itself against competitors (even if not explicitly mentioned)
    - Focus on tangible, verifiable advantages rather than generic marketing claims
    - Consider both functional benefits (what the product/service does) and emotional benefits (how it makes customers feel)

    **ANALYSIS GUIDELINES:**
    - Base insights only on evidence found in the provided content
    - Prioritize substance over marketing fluff
    - Look for patterns and consistency across different content sections
    - Consider both explicit statements and implicit messaging
    - Ensure each insight is specific, actionable, and defensible
    - Avoid generic statements that could apply to any brand
    - Limit each category to 5-8 high-quality insights rather than exhaustive lists

    **OUTPUT REQUIREMENTS:**
    - Provide exactly 5-8 insights per category!!!
    - Each insight should be concise but specific (1-2 sentences maximum)
    - Use clear, professional language free of marketing jargon
    - Ensure insights are mutually exclusive within each category
    - Rank insights by strength of evidence and strategic importance

    **Required JSON Output Format:**
    {{
    "name": "Company Name",
    "niche":..,
    "industry": ..,
    "description": ..,
    "goals": [
        "Specific goal identified from content analysis",
        "Another distinct objective with timeline if mentioned",
        "Additional goal if clearly articulated"
    ],
    "usp": [
        "Specific differentiator with competitive advantage",
        "Another unique proposition with clear benefit",
        "Additional USP if genuinely distinctive"
    ]
    }}

    **IMPORTANT:** Analyze only the content provided below. Do not make assumptions or add external knowledge about the company. Base all insights strictly on the website content evidence.

    ---

    **WEBSITE CONTENT TO ANALYZE:**
    {website_content}
"""


    model = genai.GenerativeModel("gemini-2.0-flash")
    response = model.generate_content(
        prompt
    )

    content = response.text.strip()
    # print(f"🤖 Gemini:\n{content}\n")
    try:
        print("Parsing JSON response...")
        json_match = re.search(r'\{.*\}', content, re.DOTALL)
        if json_match:
            json_str = json_match.group(0)
            brand_data = json.loads(json_str)
            print("JSON response parsed successfully.")
        else: print("json not parsed")
        # print(brand_data)
        with open("output/brand_guidelines.json", "w") as f:
            json.dump(brand_data, f, indent=4)
        
        # Update the state with brand identity information
        state['brand_guidelines'] = BrandGuideline(
            niche=brand_data.get('niche', ''),
            industry=brand_data.get('industry', ''),
            goals=brand_data.get('goals', []),
            usp=brand_data.get('usp', [])
        ).dict()
        state['niche'] = brand_data.get('niche', '')
        state['industry'] = brand_data.get('industry', '')
        state['goals'] = brand_data.get('goals', [])
        state['usp'] = brand_data.get('usp', [])
        
        return state
        
    except json.JSONDecodeError as e:
        error_msg = f"Error parsing JSON response: {str(e)}"
        print(error_msg)
        state['error'] = error_msg
        return state
    except Exception as e:
        error_msg = f"Error in brand identity analysis: {str(e)}"
        print(error_msg)
        state['error'] = error_msg
        return state