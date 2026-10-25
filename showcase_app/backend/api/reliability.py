"""Reliability and replay API endpoints"""

from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Optional
from models import ReplayExecutionResponse, ReplayHistoryItem

router = APIRouter()


def get_reliability_service(request: Request):
    """Dependency to get reliability service"""
    return request.app.state.services.reliability_service


def get_replay_service(request: Request):
    """Dependency to get replay service"""
    return request.app.state.services.replay_service


# DEPRECATED: decision trail feature disabled in showcase.
# def get_decision_trail_service(request: Request):
#     """Dependency to get decision trail service"""
#     return request.app.state.services.decision_trail_service


@router.get("/metrics")
async def get_reliability_metrics(
    pipeline_id: Optional[str] = None,
    service=Depends(get_reliability_service)
):
    """Get reliability metrics (SR, CR, PC, HIR, MA, TCL, WCT)"""
    try:
        metrics = await service.get_metrics(pipeline_id=pipeline_id)
        return metrics
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/slo")
async def get_slo_status(
    pipeline_id: Optional[str] = None,
    service=Depends(get_reliability_service)
):
    """Get SLO compliance status"""
    try:
        slo_status = await service.get_slo_status(pipeline_id=pipeline_id)
        return slo_status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/anomalies")
async def get_anomalies(
    pipeline_id: Optional[str] = None,
    limit: int = 50,
    service=Depends(get_reliability_service)
):
    """Get detected anomalies"""
    try:
        anomalies = await service.get_anomalies(
            pipeline_id=pipeline_id,
            limit=limit
        )
        return {"anomalies": anomalies}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/alerts")
async def get_alerts(
    pipeline_id: Optional[str] = None,
    active_only: bool = True,
    limit: int = 50,
    service=Depends(get_reliability_service)
):
    """Get active alerts"""
    try:
        alerts = await service.get_alerts(
            pipeline_id=pipeline_id,
            active_only=active_only,
            limit=limit
        )
        return {"alerts": alerts}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/circuit-breakers")
async def get_circuit_breaker_status(
    service=Depends(get_reliability_service)
):
    """Get circuit breaker status for all pipelines"""
    try:
        status = await service.get_circuit_breaker_status()
        return status
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/cost")
async def get_cost_metrics(
    pipeline_id: Optional[str] = None,
    service=Depends(get_reliability_service)
):
    """Get cost tracking metrics"""
    try:
        cost = await service.get_cost_metrics(pipeline_id=pipeline_id)
        return cost
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/trends")
async def get_trend_analysis(
    metric_name: str,
    pipeline_id: Optional[str] = None,
    window_size: int = 10,
    service=Depends(get_reliability_service)
):
    """Get trend analysis for a specific metric"""
    try:
        trends = await service.get_trend_analysis(
            metric_name=metric_name,
            pipeline_id=pipeline_id,
            window_size=window_size
        )
        return trends
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Event Replay Endpoints

@router.post("/replay/{job_id}", response_model=ReplayExecutionResponse)
async def replay_execution(
    job_id: str,
    use_cached: bool = False,
    service=Depends(get_replay_service)
):
    """
    Replay a pipeline execution and compare results
    
    Returns comparison between original and replay
    """
    try:
        result = await service.replay_execution(job_id, use_cached)
        return ReplayExecutionResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/replay/{job_id}/history")
async def get_replay_history(
    job_id: str,
    service=Depends(get_replay_service)
):
    """
    Get history of replays for an execution
    
    Returns list of previous replay attempts
    """
    try:
        history = await service.get_replay_history(job_id)
        history_responses = [ReplayHistoryItem(**item) for item in history]
        return {
            "job_id": job_id,
            "history": history_responses,
            "count": len(history_responses)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# DEPRECATED: Decision Trail endpoints disabled in showcase.
# The ia_modules DecisionTrailBuilder reads from live per-run StateManager /
# ToolRegistry instances that the showcase's execution flows don't retain
# after a run finishes. Re-enable only with a per-run registry that stores
# those instances keyed by job_id.
#
# @router.get("/decision-trail/{job_id}")
# async def get_decision_trail(
#     job_id: str,
#     service=Depends(get_decision_trail_service)
# ):
#     trail = await service.get_decision_trail(job_id)
#     return trail
#
#
# @router.get("/decision-trail/{job_id}/node/{node_id}")
# async def get_decision_node(
#     job_id: str,
#     node_id: str,
#     service=Depends(get_decision_trail_service)
# ):
#     node = await service.get_decision_node(job_id, node_id)
#     return node
#
#
# @router.get("/decision-trail/{job_id}/path")
# async def get_execution_path(
#     job_id: str,
#     service=Depends(get_decision_trail_service)
# ):
#     path = await service.get_execution_path(job_id)
#     return {"job_id": job_id, "path": path, "step_count": len(path)}
#
#
# @router.get("/decision-trail/{job_id}/evidence/{node_id}")
# async def get_decision_evidence(
#     job_id: str,
#     node_id: str,
#     service=Depends(get_decision_trail_service)
# ):
#     evidence = await service.get_decision_evidence(job_id, node_id)
#     return {"job_id": job_id, "node_id": node_id, "evidence": evidence, "count": len(evidence)}
#
#
# @router.get("/decision-trail/{job_id}/alternatives")
# async def get_alternative_paths(
#     job_id: str,
#     service=Depends(get_decision_trail_service)
# ):
#     alternatives = await service.get_alternative_paths(job_id)
#     return {"job_id": job_id, "alternatives": alternatives, "count": len(alternatives)}
#
#
# @router.get("/decision-trail/{job_id}/export")
# async def export_decision_trail(
#     job_id: str,
#     format: str = "json",
#     service=Depends(get_decision_trail_service)
# ):
#     exported = await service.export_trail(job_id, format)
#     return exported
