from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import Dict, Any
from controller import run_workflow  # Import your LangGraph-based controller logic

app = FastAPI(
    title="AI Research Workflow API",
    description="Trigger full research analysis using autonomous agents.",
    version="1.0.0"
)


class ResearchRequest(BaseModel):
    company_name: str


@app.post("/run", summary="Run full AI research workflow", response_model=Dict[str, Any])
def run_research(request: ResearchRequest):
    try:
        result = run_workflow(company_name=request.company_name)

        if result.get("error"):
            raise HTTPException(status_code=500, detail=result["error"])

        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Workflow failed: {str(e)}")
