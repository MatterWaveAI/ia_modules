"""
Collaboration Patterns API Endpoints

Exposes four agent collaboration patterns (consensus, debate, hierarchical,
peer-to-peer) built on top of ia_modules AgentOrchestrator.
"""

import json
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field
from typing import Dict, List, Any, Optional
from services.collaboration_service import CollaborationService

router = APIRouter(prefix="/api/collaboration", tags=["collaboration"])


def _get_service(request: Request) -> CollaborationService:
    """Fetch the container-constructed CollaborationService."""
    return request.app.state.services.collaboration_service


# ==================== REQUEST MODELS ====================

class ConsensusRequest(BaseModel):
    topic: str = Field(..., description="Proposal to vote on")
    agents: List[str] = Field(..., description="Agent names that will vote")
    strategy: str = Field(default="majority", description="majority | supermajority | unanimous | weighted")
    max_iterations: int = Field(default=3, ge=1, le=10)


class DebateRequest(BaseModel):
    topic: str = Field(..., description="Debate topic")
    proponents: List[str] = Field(..., description="Agents arguing for")
    opponents: List[str] = Field(..., description="Agents arguing against")
    moderator: str = Field(default="Moderator", description="Moderator agent name")
    rounds: int = Field(default=2, ge=1, le=5)


class HierarchicalRequest(BaseModel):
    task: str = Field(..., description="Task to delegate")
    leader: str = Field(..., description="Leader agent name")
    workers: List[str] = Field(..., description="Worker agent names")


class PeerToPeerRequest(BaseModel):
    task: str = Field(..., description="Collaborative task")
    peers: List[str] = Field(..., description="Peer agent names")
    rounds: int = Field(default=2, ge=1, le=5)


# ==================== ENDPOINTS ====================

@router.get("/patterns")
async def get_patterns(request: Request) -> Dict[str, Any]:
    """List available collaboration patterns with descriptions."""
    return {"patterns": _get_service(request).get_patterns()}


@router.post("/consensus")
async def run_consensus(body: ConsensusRequest, request: Request) -> Dict[str, Any]:
    """Run the consensus collaboration pattern."""
    try:
        svc = _get_service(request)
        return await svc.run_consensus(
            topic=body.topic,
            agents=body.agents,
            strategy=body.strategy,
            max_iterations=body.max_iterations,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/debate")
async def run_debate(body: DebateRequest, request: Request) -> Dict[str, Any]:
    """Run the debate collaboration pattern."""
    try:
        svc = _get_service(request)
        return await svc.run_debate(
            topic=body.topic,
            proponents=body.proponents,
            opponents=body.opponents,
            moderator=body.moderator,
            rounds=body.rounds,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/hierarchical")
async def run_hierarchical(body: HierarchicalRequest, request: Request) -> Dict[str, Any]:
    """Run the hierarchical collaboration pattern."""
    try:
        svc = _get_service(request)
        return await svc.run_hierarchical(
            task=body.task,
            leader=body.leader,
            workers=body.workers,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/peer-to-peer")
async def run_peer_to_peer(body: PeerToPeerRequest, request: Request) -> Dict[str, Any]:
    """Run the peer-to-peer collaboration pattern."""
    try:
        svc = _get_service(request)
        return await svc.run_peer_to_peer(
            task=body.task,
            peers=body.peers,
            rounds=body.rounds,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/executions")
async def list_collaboration_executions(request: Request, pattern: Optional[str] = None,
                                         limit: int = 20) -> Dict[str, Any]:
    """List previous collaboration pattern executions from DB."""
    exec_svc = getattr(request.app.state.services, "agent_execution_service", None)
    if not exec_svc:
        return {"executions": []}
    rows = await exec_svc.list_executions(role=pattern, limit=limit)
    # Filter to collaboration runs (agent_mode == 'collaboration')
    collab_runs = [r for r in rows if r.get("agent_mode") == "collaboration"]
    return {"executions": collab_runs}


@router.get("/executions/{run_id}")
async def get_collaboration_execution(run_id: str, request: Request) -> Dict[str, Any]:
    """Get a single collaboration execution with full result (history + result summary)."""
    exec_svc = getattr(request.app.state.services, "agent_execution_service", None)
    if not exec_svc:
        raise HTTPException(status_code=404, detail="Execution service unavailable")
    row = await exec_svc.get_execution(run_id)
    if not row:
        raise HTTPException(status_code=404, detail="Execution not found")

    # result_text stores the full JSON output from the collaboration run
    result_text = row.get("result_text", "")
    if result_text and result_text.startswith("{"):
        try:
            return json.loads(result_text)
        except (json.JSONDecodeError, ValueError):
            pass

    # Old executions without full JSON stored
    return {
        "pattern": row.get("agent_role", "unknown"),
        "run_id": run_id,
        "task": row.get("task", ""),
        "history": [],
        "result": {},
        "child_job_ids": [],
    }
