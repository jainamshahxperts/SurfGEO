import os
import json
import logging
from typing import List, Dict, Any, Optional
from langgraph.graph import StateGraph, END

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import agents
from agents.scrapper_agent import ScraperAgent
from agents.periodic_table_agent import PeriodicTableAgent
from agents.brand_identity_agent import brand_identity_agent
from agents.keyword_intelligence_agent import KeywordResearchAgent, KeywordResearchConfig
from agents.prompt_page_agent import SEOpromptAgent, SEOpromptAgentConfig
from agents.visibility_agent import AEOEvaluatorAgent, AEO_WEIGHTS
from agents.industry_agent import IndustryAgent
from agents.BrandAnalytics_agent import BrandAnalyticsAgent
from agents.schemas import ResearchState


class ResearchController:
    def __init__(self):
        """Initialize the ResearchController with all required agents and workflow configuration."""
        try:
            logger.info("Initializing ResearchController...")
            
            # Initialize all agents
            self.scrapper_agent = ScraperAgent()
            self.periodic_table_agent = PeriodicTableAgent()
            
            # brand_identity_agent is a function, not a class - we'll use it directly
            self.brand_identity_agent = brand_identity_agent
            
            # Initialize keyword research agent with config
            keyword_config = KeywordResearchConfig()
            self.keyword_intelligence_agent = KeywordResearchAgent(config=keyword_config)
            
            # Initialize prompt page agent with config
            prompt_config = SEOpromptAgentConfig()
            self.prompt_page_agent = SEOpromptAgent(config=prompt_config)
            
            # Initialize remaining agents
            self.visibility_agent = AEOEvaluatorAgent(weights=AEO_WEIGHTS)
            self.industry_agent = IndustryAgent()
            self.brand_analytics_agent = BrandAnalyticsAgent()

            # Initialize workflow with proper state structure
            self.workflow = StateGraph(ResearchState)
            
            # Set up the workflow nodes and edges
            self._setup_workflow()
            
        except Exception as e:
            logger.error(f"Failed to initialize ResearchController: {str(e)}")
            raise
            
    def _setup_workflow(self):
        """Set up the workflow nodes and edges."""
        try:
            # Add all nodes to the workflow
            self.workflow.add_node("scrape_website", self.scrapper_agent.scrape_website)
            self.workflow.add_node("brand_identity", self.brand_identity_agent)
            self.workflow.add_node("periodic_table_analysis", self.periodic_table_agent.analyze)
            self.workflow.add_node("keyword_research", self.keyword_intelligence_agent.run_research_node)
            self.workflow.add_node("prompt_page_analysis", self.prompt_page_agent.run_prompt_node)
            self.workflow.add_node("industry_analysis", self.industry_agent.run_industry_analysis)
            self.workflow.add_node("visibility_analysis", self.visibility_agent.run_visibility_node)
            self.workflow.add_node("brand_analytics", self.brand_analytics_agent.run_brand_analytics_node)
            
            # Define the workflow edges
            self.workflow.set_entry_point("scrape_website")
            
            # First parallel branch: brand identity and keyword research
            self.workflow.add_edge("scrape_website", "brand_identity")
            self.workflow.add_edge("brand_identity", "keyword_research")
            
            # Second parallel branch: periodic table analysis
            self.workflow.add_edge("scrape_website", "periodic_table_analysis")
            
            # Continue the workflow
            self.workflow.add_edge("keyword_research", "prompt_page_analysis")
            self.workflow.add_edge("prompt_page_analysis", "industry_analysis")
            self.workflow.add_edge("industry_analysis", "visibility_analysis")
            
            # Brand analytics should run only after both visibility_analysis and periodic_table_analysis complete
            # First, create a conditional edge from periodic_table_analysis to brand_analytics
            # Then ensure visibility_analysis also points to brand_analytics
            self.workflow.add_edge("visibility_analysis", "brand_analytics")
            self.workflow.add_edge("periodic_table_analysis", "brand_analytics")
            
            # Set the final node
            self.workflow.set_finish_point("brand_analytics")
            
            logger.info("Workflow graph set up successfully")
            
        except Exception as e:
            logger.error(f"Failed to set up workflow: {str(e)}")
            raise

def run_workflow(company_name: str = "example.com") -> Dict[str, Any]:
    """
    Run the complete research workflow for a given company.
    
    Args:
        company_name: Name of the company/website to analyze
        
    Returns:
        Final research state with all analysis results
    """
    try:
        logger.info(f"Starting research workflow for: {company_name}")
        
        # Initialize the controller
        controller = ResearchController()
        
        # Create initial state with proper structure for LangGraph
        from agents.schemas import ResearchState, ResearchStateModel
        
        # Initialize the state as a dictionary with all required keys
        initial_state: ResearchState = {
            'company_name': company_name,
            'brand_guidelines': None,
            'periodic_table_report': None,
            'seo_keywords': None,
            'prompt_report': None,
            'unique_competitors': None,
            'ranking_analysis_output': None,
            'visibility_report': None,
            'brand_metrics': None,
            'niche': None,
            'industry': None,
            'goals': None,
            'usp': None,
            'error': None,
            'website_content': None
        }
        
        # Validate the initial state against the Pydantic model
        try:
            validated_state = ResearchStateModel(**initial_state)
            initial_state = validated_state.dict()
        except Exception as e:
            logger.error(f"Invalid initial state: {str(e)}")
            raise ValueError(f"Invalid initial state: {str(e)}")
        
        # Compile the workflow
        logger.info("Compiling workflow...")
        app = controller.workflow.compile()
        
        # Run the workflow
        logger.info("Executing workflow...")
        final_state = app.invoke(initial_state)
        
        # Save results
        os.makedirs("output", exist_ok=True)
        output_path = os.path.join("output", "final_results.json")
        
        try:
            # Convert the final state to a serializable format
            serializable_state = {}
            for key, value in final_state.items():
                if hasattr(value, 'dict'):
                    serializable_state[key] = value.dict()
                elif isinstance(value, (list, dict, str, int, float, bool, type(None))):
                    serializable_state[key] = value
                else:
                    serializable_state[key] = str(value)
            
            # Save to file
            with open(output_path, "w", encoding='utf-8') as f:
                json.dump(serializable_state, f, indent=2, ensure_ascii=False, default=str)
                
            logger.info(f"Research workflow completed successfully! Results saved to {output_path}")
            return final_state
            
        except Exception as e:
            logger.error(f"Error saving results: {str(e)}")
            # Return the final state even if saving fails
            return final_state
        
    except Exception as e:
        error_msg = f"Error in research workflow: {str(e)}"
        logger.error(error_msg)
        print(f"\n{error_msg}\n")
        print("Research workflow failed. Check the logs for more details.")
        return {"error": error_msg}

if __name__ == "__main__":
    try:
        # Ask for user input at runtime
        company_name = input("Enter the company name or website to analyze: ").strip()
        if not company_name:
            raise ValueError("Company name cannot be empty.")
        
        # Run the workflow
        final_state = run_workflow(company_name=company_name)
        
        # Print summary of results
        print("\n" + "="*50)
        print(f"Research Results for: {company_name}")
        print("="*50)
        
        # Display key metrics
        if final_state.get("brand_metrics"):
            print("\nBrand Metrics:")
            for key, value in final_state["brand_metrics"].items():
                print(f"- {key.replace('_', ' ').title()}: {value}")
        
        if final_state.get("industry_analysis"):
            print("\nIndustry Analysis:")
            print(f"Total Mentions: {final_state['industry_analysis'].get('total_mentions', 0)}")
            print(f"Unique Companies: {final_state['industry_analysis'].get('unique_companies', 0)}")
        
        print("\nResearch completed successfully!")
        print("Detailed results are available in the output/ directory.")
        
    except Exception as e:
        print(f"\nError: {str(e)}")
        print("Research workflow failed. Check the logs for more details.")
        exit(1)
