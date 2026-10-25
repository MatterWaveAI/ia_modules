"""Checkpoint API endpoints"""

from fastapi import APIRouter, HTTPException, Depends, Request
from models import CheckpointResponse, CheckpointStateResponse, CheckpointResumeResponse

router = APIRouter()


def get_checkpoint_service(request: Request):
    """Dependency to get checkpoint service"""
    return request.app.state.services.checkpoint_service


@router.get("/{job_id}")
async def list_checkpoints(
    job_id: str,
    service=Depends(get_checkpoint_service)
):
    """List all checkpoints for a specific execution"""
    try:
        checkpoints = await service.list_checkpoints(job_id)
        checkpoint_responses = [CheckpointResponse(**cp) for cp in checkpoints]
        return {"job_id": job_id, "checkpoints": checkpoint_responses, "count": len(checkpoint_responses)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/checkpoint/{checkpoint_id}", response_model=CheckpointResponse)
async def get_checkpoint(
    checkpoint_id: str,
    service=Depends(get_checkpoint_service)
):
    """Get checkpoint details"""
    try:
        checkpoint = await service.get_checkpoint(checkpoint_id)
        if not checkpoint:
            raise HTTPException(status_code=404, detail="Checkpoint not found")
        return CheckpointResponse(**checkpoint)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/checkpoint/{checkpoint_id}/state", response_model=CheckpointStateResponse)
async def get_checkpoint_state(
    checkpoint_id: str,
    service=Depends(get_checkpoint_service)
):
    """Get checkpoint state data"""
    try:
        state = await service.get_checkpoint_state(checkpoint_id)
        if state is None:
            raise HTTPException(status_code=404, detail="Checkpoint not found")
        return CheckpointStateResponse(checkpoint_id=checkpoint_id, state=state)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/checkpoint/{checkpoint_id}/resume", response_model=CheckpointResumeResponse)
async def resume_from_checkpoint(
    checkpoint_id: str,
    service=Depends(get_checkpoint_service)
):
    """Resume pipeline execution from a checkpoint"""
    try:
        result = await service.resume_from_checkpoint(checkpoint_id)
        return CheckpointResumeResponse(**result)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
