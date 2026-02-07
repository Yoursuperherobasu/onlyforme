from fastapi import APIRouter, Depends, HTTPException

from agentcore.graph_langgraph import GraphDump

router = APIRouter(prefix="/starter-projects", tags=["Flows"])


@router.get("/", status_code=200)
async def get_starter_projects() -> list[GraphDump]:
    """Get a list of starter projects."""
    
    try:
        return ""
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc
