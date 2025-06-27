from pydantic import BaseModel, Field
from typing import Optional, List, Annotated,Dict
from typing_extensions import TypedDict

def reduce_company_name(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Keep the existing company_name if it exists, otherwise use the new value."""
    return existing or new

from typing import Dict

def reduce_website_content(existing: Optional[Dict], new: Optional[Dict]) -> Optional[Dict]:
    """Keep the existing website_content if it exists, otherwise use the new value."""
    return existing or new

def reduce_periodic_table(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Keep the existing periodic_table if it exists, otherwise use the new value."""
    return existing or new

def reduce_brand_guidelines(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Keep the existing brand_guidelines if it exists, otherwise use the new value."""
    return existing or new

def reduce_seo_keywords(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Keep the existing seo_keywords if it exists, otherwise use the new value."""
    return existing or new     

def reduce_prompt_report(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Keep the existing prompt_report if it exists, otherwise use the new value."""
    return existing or new     

def reduce_unique_competitors(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Keep the existing unique_competitors if it exists, otherwise use the new value."""
    return existing or new     

def reduce_ranking_analysis_output(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Keep the existing ranking_analysis_output if it exists, otherwise use the new value."""
    return existing or new     

def reduce_visibility_report(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Keep the existing visibility_report if it exists, otherwise use the new value."""
    return existing or new     

def reduce_brand_metrics(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Keep the existing brand_metrics if it exists, otherwise use the new value."""
    return existing or new     

def reduce_niche(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Keep the existing niche if it exists, otherwise use the new value."""
    return existing or new     

def reduce_industry(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Keep the existing industry if it exists, otherwise use the new value."""
    return existing or new     

def reduce_goals(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Keep the existing goals if it exists, otherwise use the new value."""
    return existing or new     

def reduce_usp(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Keep the existing usp if it exists, otherwise use the new value."""
    return existing or new     

def reduce_error(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Prioritize the new error if it exists, otherwise keep the existing value."""
    return new or existing     

def reduce_similar_web_data(existing: Optional[dict], new: Optional[dict]) -> Optional[dict]:
    """Keep the existing similar_web_data if it exists, otherwise use the new value."""
    return existing or new

def reduce_niche(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Keep the existing niche if it exists, otherwise use the new value."""
    return existing or new     

def reduce_industry(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Keep the existing industry if it exists, otherwise use the new value."""
    return existing or new     

def reduce_goals(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Keep the existing goals if it exists, otherwise use the new value."""
    return existing or new     

def reduce_usp(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Keep the existing usp if it exists, otherwise use the new value."""
    return existing or new     

def reduce_error(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Keep the existing error if it exists, otherwise use the new value."""
    return existing or new     

def reduce_website_content_individual(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Keep the existing website_content_individual if it exists, otherwise use the new value."""
    return existing or new

def reduce_compatibility_report(existing: Optional[dict], new: Optional[dict]) -> Optional[dict]:
    """Keep the existing compatibility_report if it exists, otherwise use the new value."""
    return existing or new     

def reduce_audit_report(existing: Optional[dict], new: Optional[dict]) -> Optional[dict]:
    """Keep the existing audit_report if it exists, otherwise use the new value."""
    return existing or new     

def reduce_scraped_summary(existing: Optional[str], new: Optional[str]) -> Optional[str]:
    """Keep the existing scrapped_summary if it exists, otherwise use the new value."""
    return existing or new     

class PeriodicTable(BaseModel):
    Content_Quality_And_Depth: int
    Trustworthiness_And_Credibility: int
    Content_Relevance: int
    Citations_And_Mentions_In_Trusted_Sources: int
    Topical_Authority_And_Expertise: int
    Search_Engine_Rankings_Bing_Google: int
    Verifiable_Performance_Metrics: int
    Sentiment_Analysis: int
    Data_Frequency_And_Consistency: int
    Social_Proof_And_Reviews: int
    Structured_Data_Schema_Markup: int
    Content_Freshness_And_Timeliness: int
    Technical_Performance_Speed_Mobile: int
    Localization: int
    Social_Signals: int

class BrandGuideline(BaseModel):
    niche: str
    industry: str
    goals: List[str]
    usp: List[str]

# Define a state dictionary type for LangGraph
class ResearchState(TypedDict, total=False):
    """State for the research workflow."""
    # Core fields
    company_name: Annotated[str, reduce_company_name]
    scraped_summary: Annotated[Optional[str], reduce_scraped_summary]
    website_content: Annotated[Optional[Dict], reduce_website_content]
    website_content_individual: Annotated[Optional[dict], reduce_website_content]
    compatibility_report: Annotated[Optional[dict], reduce_compatibility_report]
    brand_guidelines: Annotated[Optional[BrandGuideline], reduce_brand_guidelines]
    periodic_table_report: Annotated[Optional[dict], reduce_periodic_table]
    seo_keywords: Annotated[Optional[List[str]], reduce_seo_keywords]
    prompt_report: Annotated[Optional[dict], reduce_prompt_report]
    unique_competitors: Annotated[Optional[List[str]], reduce_unique_competitors]
    ranking_analysis_output: Annotated[Optional[dict], reduce_ranking_analysis_output]
    visibility_report: Annotated[Optional[dict], reduce_visibility_report]
    brand_metrics: Annotated[Optional[dict], reduce_brand_metrics]
    similar_web_data: Annotated[Optional[dict], reduce_similar_web_data]
    audit_report: Annotated[Optional[dict], reduce_audit_report]
    
    # Additional fields used in the workflow
    niche: Annotated[Optional[str], reduce_niche]
    industry: Annotated[Optional[str], reduce_industry]
    goals: Annotated[Optional[List[str]], reduce_goals]
    usp: Annotated[Optional[List[str]], reduce_usp]
    error: Annotated[Optional[str], reduce_error]

# For backward compatibility, keep the Pydantic model
class ResearchStateModel(BaseModel):
    """Pydantic model for ResearchState (for validation)."""
    company_name: Annotated[str, "company_name"]
    scraped_summary: Annotated[Optional[str], "scraped_summary"] = None
    website_content: Optional[Dict] = None
    website_content_individual: Optional[dict] = None
    brand_guidelines: Optional[BrandGuideline] = None
    periodic_table_report: Optional[dict] = None
    seo_keywords: Optional[List[str]] = None
    prompt_report: Optional[dict] = None
    unique_competitors: Optional[List[str]] = None
    ranking_analysis_output: Optional[dict] = None
    visibility_report: Optional[dict] = None
    brand_metrics: Optional[dict] = None
    similar_web_data: Optional[dict] = None
    
    # Additional fields used in the workflow
    niche: Annotated[Optional[str], "niche"] = None
    industry: Annotated[Optional[str], "industry"] = None
    goals: Annotated[Optional[List[str]], "goals"] = None
    usp: Annotated[Optional[List[str]], "usp"] = None
    error: Annotated[Optional[str], "error"] = None
    compatibility_report: Optional[dict] = None
    audit_report: Optional[dict] = None
    
    class Config:
        arbitrary_types_allowed = True