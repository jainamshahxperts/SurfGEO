import google.generativeai as genai
from .schemas import PeriodicTable, ResearchState
import json
from dotenv import load_dotenv
import os
import re
from typing import Optional, Dict, Any, TYPE_CHECKING
import logging
from pydantic import BaseModel

if TYPE_CHECKING:
    from .schemas import ResearchState

load_dotenv()
genai.configure(api_key=os.getenv("GOOGLE_API_KEY"))

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class PeriodicTableAgent:
    def __init__(self):
        self.model = genai.GenerativeModel("gemini-2.0-flash")
        self.aeo_variables = [
            "Content Quality & Depth",
            "Trustworthiness & Credibility", 
            "Content Relevance",
            "Citations & Mentions in Trusted Sources",
            "Topical Authority & Expertise",
            "Search Engine Rankings (Bing, Google)",
            "Verifiable Performance Metrics",
            "Sentiment Analysis",
            "Data Frequency & Consistency",
            "Social Proof and Reviews",
            "Structured Data (Schema Markup, etc.)",
            "Content Freshness & Timeliness",
            "Technical Performance (Speed, Mobile)",
            "Localization",
            "Social Signals"
        ]
        self.geo_checklist="""
            1. Content Quality & Depth
            - Ensure the content is comprehensive and covers the topic thoroughly
            - Include examples, visuals, tables, and references where applicable
            - Avoid thin, repetitive, or keyword-stuffed content

            2. Trustworthiness & Credibility
            - Clearly state sources of information and data
            - Provide author bios with credentials or expertise
            - Include disclaimers, privacy policy, and editorial standards

            3. Content Relevance
            - Match the content closely to the specific query intent (informational, transactional, etc.)
            - Use relevant keywords naturally without over-optimization
            - Keep the content focused on the topic without unnecessary tangents

            4. Citations & Mentions in Trusted Sources
            - Link out to authoritative sources like academic journals, .gov or .edu sites
            - Earn inbound mentions or backlinks from reputable industry sites
            - Ensure citations are up to date and factually accurate

            5. Topical Authority & Expertise
            - Build a content cluster covering subtopics thoroughly
            - Publish regularly in your niche to build domain topical depth
            - Show expertise through case studies, whitepapers, or expert interviews

            6. Search Engine Rankings (Bing, Google)
            - Monitor keyword positions using tools like GSC, Semrush
            - Optimize titles, descriptions, and schema for rich snippets
            - Evaluate performance against competitors on key terms

            7. Verifiable Performance Metrics
            - Include performance KPIs (e.g., conversion rate, ROI, traffic growth)
            - Use graphs, benchmarks, and analytics to support claims
            - Back up statements with quantified results and measurable impact

            8. Sentiment Analysis
            - Ensure the tone is helpful, constructive, and positive
            - Address any negative topics with transparency and empathy
            - Use natural language that aligns with voice assistants and answer engines

            9. Data Frequency & Consistency
            - Regularly review and update statistics and claims
            - Sync data across all content formats (blogs, case studies, landing pages)
            - Avoid contradictory or outdated facts

            10. Social Proof and Reviews
            - Embed real customer testimonials, ratings, and endorsements
            - Display user engagement metrics (shares, likes, comments)
            - Reference community or customer involvement in brand storytelling

            11. Structured Data (Schema Markup, etc.)
            - Implement correct schema.org types (e.g., Article, FAQ, Review)
            - Use JSON-LD format for compatibility
            - Validate markup using Google’s Rich Results Testing Tool

            12. Content Freshness & Timeliness
            - Keep publishing dates visible and update old content regularly
            - Highlight recent developments or breaking news in your field
            - Remove obsolete sections or replace them with updated insights

            13. Technical Performance (Speed, Mobile)
            - Optimize page speed (Core Web Vitals, lazy loading, image compression)
            - Ensure full mobile responsiveness and readability
            - Use clean HTML/CSS and avoid bloated scripts

            14. Localization
            - Adapt language, currency, and references to target audience regions
            - Use hreflang tags where applicable
            - Incorporate local events, case studies, and cultural context

            15. Social Signals
            - Promote content on platforms like LinkedIn, X, Reddit, YouTube
            - Encourage sharing through CTAs and embedded buttons
            - Track and respond to engagement for feedback loops     
        """

    def _create_aeo_prompt(self, website_content: str) -> str:
        # print("website_contenttt", website_content)
        return f"""
        You are a senior Answer Engine Optimization (AEO) specialist with expertise in AI-powered search engines, voice assistants, and conversational AI systems. 

        Evaluate the following website content and assign a precise score from 0-10 for each AEO variable:

        **AEO Variables to Score:**
        {chr(10).join(f"{i+1}. {var}" for i, var in enumerate(self.aeo_variables))}

        **Scoring Guidelines:**
        - 0-20: Poor/Absent - Variable missing or severely deficient
        - 30-40: Below Average - Present but poorly implemented  
        - 50-60: Average - Meets basic standards without optimization
        - 70-80: Good - Well-implemented with clear optimization effort
        - 90-10: Excellent - Expertly optimized for answer engines

        **Critical Requirements:**
        - Provide exactly one score (0-100) for each variable
        - Base scores strictly on evidence in the provided content
        - Consider how answer engines would interpret this content
        - Focus on user intent satisfaction and information accessibility
        - don't necessarily rank in multiples of 5

        **Judge on the bases of:**
        {self.geo_checklist}

        **Required JSON Output Format:**
        {{
{chr(10).join(f'            "{var}": 0,' for var in self.aeo_variables[:-1])}
            "{self.aeo_variables[-1]}": 0
        }}

        **Website Content to Evaluate:**
        {website_content}
        """

    def _extract_json_from_response(self, response_text: str) -> Optional[Dict[str, Any]]:
        try:
            json_match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', response_text, re.DOTALL)
            if json_match:
                return json.loads(json_match.group(0))
            return json.loads(response_text.strip())
        except json.JSONDecodeError as e:
            logger.error(f"JSON parsing error: {e}")
            logger.debug(f"Response content: {response_text[:500]}...")
            return None

    def _validate_aeo_scores(self, scores: Dict[str, Any]) -> Dict[str, int]:
        validated_scores = {}
        for variable in self.aeo_variables:
            if variable in scores:
                try:
                    score = int(scores[variable])
                    validated_scores[variable] = max(0, min(100, score))
                except (ValueError, TypeError):
                    logger.warning(f"Invalid score for {variable}: {scores[variable]}. Setting to 0.")
                    validated_scores[variable] = 0
            else:
                logger.warning(f"Missing score for {variable}. Setting to 0.")
                validated_scores[variable] = 0
        return validated_scores

    def _save_analysis_results(self, analysis_data: Dict[str, Any], filename: str = "aeo_analysis.json") -> None:
        try:
            with open(filename, "w", encoding='utf-8') as f:
                json.dump(analysis_data, f, indent=4, ensure_ascii=False)
            logger.info(f"Analysis results saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving analysis results: {e}")

    def analyze(self, state: ResearchState) -> ResearchState:
        """
        Analyze the website content and update the state with periodic table analysis.
        
        Args:
            state: The current research state containing website content (dictionary)
            
        Returns:
            Updated research state with periodic table analysis
        """
        print("Starting periodic table analysis...")
        
        if not state.get('website_content'):
            error_msg = "No website content available for analysis."
            print(f"Error: {error_msg}")
            state['error'] = error_msg
            return state
            
        try:
            # Parse the website content if it's a JSON string
            try:
                content_data = state['website_content']
                print("Extracting content from compiled data...")
                
                # Get compiled content from the nested structure
                compiled_content = content_data.get("compiled_content", {})
                
                # Extract and join all the content
                content_parts = [
                    " ".join(compiled_content.get("all_h1_titles", [])),
                    " ".join(compiled_content.get("all_h2_titles", [])),
                    "\n".join(compiled_content.get("all_paragraphs", [])),
                    " ".join([f"{faq.get('question', '')} {faq.get('answer', '')}" for faq in compiled_content.get("all_faq", [])])
                ]
                
                content_text = "\n".join(filter(None, content_parts))
            except (AttributeError, TypeError) as e:
                print(f"Warning: Could not process website content: {str(e)}")
                content_text = str(state['website_content'])  # fallback to string version
            
            # Create prompt and get response from the model
            prompt = self._create_aeo_prompt(content_text)
            response = self.model.generate_content(prompt)
            content = response.text.strip()
            
            logger.info("Parsing JSON response...")
            print("Parsing JSON response for periodic table...")
            
            # Extract and validate the JSON response
            periodic_table_data = self._extract_json_from_response(content)
            if not periodic_table_data:
                raise ValueError("No valid JSON data found in the model's response")
            
            print("Periodic table data:", periodic_table_data)
            # Validate and process the scores
            validated_scores = self._validate_aeo_scores(periodic_table_data)
            
            # Save the analysis results to a file
            self._save_analysis_results(validated_scores, filename="output/periodic_table.json")
            
            # Create a PeriodicTable instance
            periodic_table = PeriodicTable(
                Content_Quality_And_Depth=validated_scores.get("Content Quality & Depth", 0),
                Trustworthiness_And_Credibility=validated_scores.get("Trustworthiness & Credibility", 0),
                Content_Relevance=validated_scores.get("Content Relevance", 0),
                Citations_And_Mentions_In_Trusted_Sources=validated_scores.get("Citations & Mentions in Trusted Sources", 0),
                Topical_Authority_And_Expertise=validated_scores.get("Topical Authority & Expertise", 0),
                Search_Engine_Rankings_Bing_Google=validated_scores.get("Search Engine Rankings (Bing, Google)", 0),
                Verifiable_Performance_Metrics=validated_scores.get("Verifiable Performance Metrics", 0),
                Sentiment_Analysis=validated_scores.get("Sentiment Analysis", 0),
                Data_Frequency_And_Consistency=validated_scores.get("Data Frequency & Consistency", 0),
                Social_Proof_And_Reviews=validated_scores.get("Social Proof and Reviews", 0),
                Structured_Data_Schema_Markup=validated_scores.get("Structured Data (Schema Markup, etc.)", 0),
                Content_Freshness_And_Timeliness=validated_scores.get("Content Freshness & Timeliness", 0),
                Technical_Performance_Speed_Mobile=validated_scores.get("Technical Performance (Speed, Mobile)", 0),
                Localization=validated_scores.get("Localization", 0),
                Social_Signals=validated_scores.get("Social Signals", 0)
            )
            
            # Update the state with the periodic table report
            state['periodic_table_report'] = periodic_table.dict()
            print(" Periodic table analysis completed successfully")
            
            return state
            
        except Exception as e:
            error_msg = f"Error in periodic table analysis: {str(e)}"
            logger.error(error_msg)
            state['error'] = error_msg
            return state

class ResearchState(BaseModel):
    website_content: dict
    periodic_table_report: dict = {}
    error: str = ""

# Example use:
# agent = PeriodicTableAgent()
# result = agent.analyze(state)
# mock_content = """
# Welcome to ClimateTech Solutions! We help enterprises transition to sustainable energy with our expert-backed analytics, performance dashboards, and climate-compliant certifications. Featured in Forbes, Bloomberg, and Wired. Trusted by over 5,000 businesses worldwide.
# """

# # Create a fake `state` object
# mock_state = SimpleNamespace(
#     content=mock_content,
#     company="ClimateTech Solutions"
# )

# with open("output/website_content_compiled.json","r",encoding="utf-8") as f:
#     content=json.load(f)
#     content = content["compiled_content"]

# mock_state = SimpleNamespace(
#     content=content,
#     company="Weboccult"
# )

# # Run the agent
# agent = PeriodicTableAgent()
# result = agent.analyze(mock_state)

# # Print result
# print(result)
