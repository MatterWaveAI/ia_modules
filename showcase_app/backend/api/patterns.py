"""
Agentic Patterns API Endpoints

Exposes the PatternService (reflection, planning, tool use, agentic RAG,
metacognition) over HTTP so the frontend PatternsPage can execute them.
"""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from services.pattern_service import PatternService

router = APIRouter(prefix="/api/patterns", tags=["patterns"])


def _get_service(request: Request) -> PatternService:
    """Fetch the container-constructed PatternService."""
    return request.app.state.services.pattern_service


# ==================== REQUEST MODELS ====================

class ReflectionRequest(BaseModel):
    initial_output: str = Field(..., description="Text to improve via reflection")
    criteria: Dict[str, str] = Field(..., description="Quality criteria keyed by name")
    max_iterations: int = Field(default=3, ge=1, le=10)


class PlanningRequest(BaseModel):
    goal: str = Field(..., description="High-level goal to decompose")
    constraints: Optional[Dict[str, Any]] = None


class ToolUseRequest(BaseModel):
    task: str = Field(..., description="Task to accomplish")
    available_tools: List[str] = Field(..., description="Available tool names")


class AgenticRAGRequest(BaseModel):
    query: str = Field(default="", description="Initial search query")
    initial_query: str = Field(default="", description="Alias for query")
    max_refinements: int = Field(default=3, ge=1, le=10)


class MetacognitionRequest(BaseModel):
    execution_trace: List[Dict[str, Any]] = Field(..., description="History of agent actions")
    performance_metrics: Dict[str, float] = Field(..., description="Performance measurements")


# ==================== ENDPOINTS ====================

@router.post("/reflection")
async def run_reflection(body: ReflectionRequest, request: Request) -> Dict[str, Any]:
    """Run the reflection pattern: self-critique and iterative improvement"""
    try:
        return await _get_service(request).reflection_example(
            initial_output=body.initial_output,
            criteria=body.criteria,
            max_iterations=body.max_iterations
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/planning")
async def run_planning(body: PlanningRequest, request: Request) -> Dict[str, Any]:
    """Run the planning pattern: goal decomposition into steps"""
    try:
        return await _get_service(request).planning_example(
            goal=body.goal,
            constraints=body.constraints
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/tool-use")
async def run_tool_use(body: ToolUseRequest, request: Request) -> Dict[str, Any]:
    """Run the tool use pattern: dynamic tool selection and planning"""
    try:
        return await _get_service(request).tool_use_example(
            task=body.task,
            available_tools=body.available_tools
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/agentic-rag")
async def run_agentic_rag(body: AgenticRAGRequest, request: Request) -> Dict[str, Any]:
    """Run the agentic RAG pattern: query refinement and retrieval"""
    try:
        query = body.query or body.initial_query
        if not query:
            raise ValueError("Either 'query' or 'initial_query' is required")
        return await _get_service(request).agentic_rag_example(
            initial_query=query,
            max_refinements=body.max_refinements
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/metacognition")
async def run_metacognition(body: MetacognitionRequest, request: Request) -> Dict[str, Any]:
    """Run the metacognition pattern: self-monitoring and adaptation"""
    try:
        return await _get_service(request).metacognition_example(
            execution_trace=body.execution_trace,
            performance_metrics=body.performance_metrics
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
