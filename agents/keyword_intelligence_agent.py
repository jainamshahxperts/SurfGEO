from typing import List, Dict, Optional
import json
import logging
import os
import google.generativeai as genai
from pydantic import BaseModel
from agents.schemas import ResearchState

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Configure Google GenAI API
try:
    genai.configure(api_key=os.environ["GOOGLE_API_KEY"])
except KeyError:
    logger.error("GOOGLE_API_KEY environment variable not set")
    raise EnvironmentError("Please set the GOOGLE_API_KEY environment variable")

# Keyword prompt template
KEYWORD_PROMPT_TEMPLATE = """
You are an expert SEO strategist with 15+ years of experience in keyword research, competitive analysis, and search intent optimization. Generate 90–100 strategically targeted SEO keywords and search phrases for the '{niche}' niche within the '{industry}' industry.
Keyword Requirements:
Search Intent Coverage (distribute evenly):

Informational Intent: Educational content, guides, definitions, comparisons
Commercial Intent: Product research, reviews, "best of" lists, vendor comparisons
Transactional Intent: Purchase-focused, pricing, demos, trials, consultations
Navigational Intent: Brand-specific, location-based, service-specific searches

User Journey Targeting:

Awareness Stage: Problem identification, trend research, industry insights
Consideration Stage: Solution evaluation, feature comparisons, case studies
Decision Stage: Implementation guides, vendor selection, ROI analysis
Retention Stage: Optimization, troubleshooting, advanced strategies

Keyword Categories to Include:

Pain Point Keywords: Common challenges, problems, obstacles, failures
Solution-Oriented: How-to guides, step-by-step processes, implementation strategies
Comparative Analysis: Versus competitors, alternative solutions, feature comparisons
Tool & Resource: Software, platforms, automation, management systems
Financial Focus: Cost analysis, pricing models, ROI calculation, budget planning
Compliance & Standards: Regulations, certifications, audit requirements, governance
Performance Metrics: KPIs, benchmarks, measurement, analytics, reporting
Industry-Specific: Sector terminology, vertical-specific challenges, niche applications
Temporal & Trending: Current year trends, future predictions, emerging technologies
Geographic & Demographic: Location-based, company size-specific, role-based

Technical SEO Considerations:

Include long-tail keywords (4+ words) for easier ranking opportunities
Mix of head terms (1-2 words) and long-tail variations
Consider voice search patterns and question-based queries
Include local SEO variations where applicable
Incorporate seasonal and trending modifiers

Ranking Difficulty Algorithm:
Calculate ranking score (5-95) based on:

Competition Level: Commercial keywords (+20-30), niche-specific (-10-15)
Search Volume Indicators: Generic terms (+15-25), specific long-tail (-10-20)
Content Type: Transactional (+20-30), informational (-5-15)
Industry Maturity: Established sectors (+10-20), emerging niches (-10-15)
Keyword Length: 1-2 words (+20-30), 4+ words (-10-20)
Question Format: "How to" (-5-10), "What is" (-10-15)

Output Format:
Provide results as a clean JSON array with this exact structure:
{{
    "keyword": "specific keyword phrase",
    "Ranking_Score": 45
}}

Quality Standards:

No duplicate or near-duplicate keywords
Maintain natural language flow and readability
Ensure commercial relevance to the specified niche and industry
Balance between competitive head terms and achievable long-tail opportunities
Include actionable, search-worthy phrases that real users would type
Verify logical ranking score distribution (mix of easy, moderate, and difficult keywords)

Advanced Considerations:

Incorporate semantic keyword variations and LSI terms
Include problem-solution keyword pairs
Consider buyer persona language and terminology
Add industry jargon and professional terminology where appropriate
Include acronyms, abbreviations, and technical terms relevant to the niche
Factor in mobile and voice search optimization patterns

Generate keywords that support a comprehensive content marketing strategy, covering all stages of the customer journey while maintaining focus on the specified niche and industry context.
"""

class KeywordResearchConfig(BaseModel):
    """Configuration for KeywordResearchAgent."""
    max_keywords: int = 60
    min_keywords: int = 50
    default_ranking_score: int = 50
    model_name: str = "gemini-2.0-flash"

class KeywordResearchAgent:
    def __init__(self, config: Optional[KeywordResearchConfig] = None):
        """Initialize the KeywordResearchAgent."""
        self.config = config or KeywordResearchConfig()
        self.model = genai.GenerativeModel(self.config.model_name)
        logger.info("KeywordResearchAgent initialized with config: %s", self.config.dict())

    def generate_keywords(self, niche: str, industry: str, goals: List[str], usp: List[str]) -> List[Dict[str, any]]:
        """
        Generate SEO-optimized keywords using Google's Gemini LLM.

        Args:
            niche: The specific niche (e.g., "cloud computing").
            industry: The broader industry (e.g., "technology").
            goals: List of business goals (e.g., ["increase brand awareness", "drive traffic"]).
            usp: List of unique selling propositions (e.g., ["cost-effective solutions", "24/7 support"]).

        Returns:
            List of dictionaries with keywords and Ranking Scores.
        """
        try:
            logger.info("Generating keywords for niche: %s, industry: %s", niche, industry)

            # Prepare the prompt
            prompt = KEYWORD_PROMPT_TEMPLATE.format(
                niche=niche,
                industry=industry,
                goals=", ".join(goals) if goals else "no specific goals provided",
                usp=", ".join(usp) if usp else "no specific USPs provided"
            )

            # Call Gemini LLM
            response = self.model.generate_content(prompt)
            if not response.text:
                logger.error("Empty response from Gemini LLM")
                return []

            # Parse the response (assuming Gemini returns JSON-formatted text)
            try:
                keywords = json.loads(response.text.strip("```json\n").strip("```"))
            except json.JSONDecodeError as e:
                logger.error("Failed to parse Gemini response as JSON: %s", str(e))
                return []

            # Validate and limit keywords
            if not isinstance(keywords, list):
                logger.error("Gemini response is not a list")
                return []

            # Ensure 90–100 keywords
            keywords = keywords[:self.config.max_keywords]
            if len(keywords) < self.config.min_keywords:
                logger.warning("Generated %d keywords, adding fillers to reach %d", len(keywords), self.config.min_keywords)
                for i in range(self.config.min_keywords - len(keywords)):
                    keywords.append({
                        "keyword": f"{niche} keyword {i+1}",
                        "Ranking_Score": self.config.default_ranking_score
                    })

            # Validate keyword format
            valid_keywords = []
            for kw in keywords:
                if isinstance(kw, dict) and "keyword" in kw and "Ranking_Score" in kw:
                    try:
                        kw["Ranking_Score"] = int(kw["Ranking_Score"])
                        if 0 <= kw["Ranking_Score"] <= 100:
                            valid_keywords.append(kw)
                    except (TypeError, ValueError):
                        logger.warning("Invalid Ranking_Score for keyword: %s", kw.get("keyword"))
                else:
                    logger.warning("Invalid keyword format: %s", kw)

            logger.info("Generated %d valid keywords", len(valid_keywords))
            return valid_keywords

        except Exception as e:
            logger.error("Error generating keywords: %s", str(e))
            return []

    def run_research_node(self, state: ResearchState) -> ResearchState:
        """
        Run the keyword research node for the LangGraph workflow.

        Args:
            state: Current research state.

        Returns:
            Updated research state with seo_keywords.
        """
        try:
            logger.info("Running KeywordResearchAgent node for company: %s", state["company_name"])

            # Extract inputs from state
            niche = state.get("niche") or "unknown_niche"
            industry = state.get("industry") or "unknown_industry"
            goals = state.get("goals") or []
            usp = state.get("usp") or []

            # Generate keywords
            keywords = self.generate_keywords(niche, industry, goals, usp)

            # Update state with only keyword strings
            state["seo_keywords"] = [kw["keyword"] for kw in keywords]
            logger.info("Keyword research completed successfully")
            with open("output/seo_keywords.json", "w", encoding='utf-8') as f:
                json.dump(keywords, f, indent=4)   
            return state

        except Exception as e:
            logger.error("Error in KeywordResearchAgent node: %s", str(e))
            state["error"] = f"Keyword research failed: {str(e)}"
            return state