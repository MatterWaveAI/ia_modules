"""Scheduler and job management API endpoints"""

from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, Optional
from pydantic import BaseModel

router = APIRouter()


class JobCreateRequest(BaseModel):
    job_name: str
    pipeline_id: str
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    input_data: Dict[str, Any] = {}
    enabled: bool = True


class JobUpdateRequest(BaseModel):
    job_name: Optional[str] = None
    cron_expression: Optional[str] = None
    interval_seconds: Optional[int] = None
    input_data: Optional[Dict[str, Any]] = None
    enabled: Optional[bool] = None


def get_scheduler_service():
    """Dependency to get scheduler service"""
    from main import get_scheduler_service
    return get_scheduler_service()


@router.post("/")
async def create_job(
    request: JobCreateRequest,
    service=Depends(get_scheduler_service)
):
    """Create a scheduled job"""
    try:
        if not request.cron_expression and not request.interval_seconds:
            raise HTTPException(
                status_code=400,
                detail="Either cron_expression or interval_seconds must be provided"
            )

        job_id = await service.create_job(
            job_name=request.job_name,
            pipeline_id=request.pipeline_id,
            cron_expression=request.cron_expression,
            interval_seconds=request.interval_seconds,
            input_data=request.input_data,
            enabled=request.enabled
        )

        job = await service.get_job(job_id)
        return job
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/")
async def list_jobs(
    pipeline_id: Optional[str] = None,
    enabled_only: bool = False,
    service=Depends(get_scheduler_service)
):
    """List all scheduled jobs"""
    try:
        jobs = await service.list_jobs(
            pipeline_id=pipeline_id,
            enabled_only=enabled_only
        )
        return {"jobs": jobs}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}")
async def get_job(
    job_id: str,
    service=Depends(get_scheduler_service)
):
    """Get job details"""
    try:
        job = await service.get_job(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        return job
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.patch("/{job_id}")
async def update_job(
    job_id: str,
    request: JobUpdateRequest,
    service=Depends(get_scheduler_service)
):
    """Update a scheduled job"""
    try:
        success = await service.update_job(
            job_id=job_id,
            job_name=request.job_name,
            cron_expression=request.cron_expression,
            interval_seconds=request.interval_seconds,
            input_data=request.input_data,
            enabled=request.enabled
        )

        if not success:
            raise HTTPException(status_code=404, detail="Job not found")

        job = await service.get_job(job_id)
        return job
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{job_id}")
async def delete_job(
    job_id: str,
    service=Depends(get_scheduler_service)
):
    """Delete a scheduled job"""
    try:
        success = await service.delete_job(job_id)
        if not success:
            raise HTTPException(status_code=404, detail="Job not found")
        return {"message": "Job deleted successfully"}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/{job_id}/run")
async def run_job_now(
    job_id: str,
    service=Depends(get_scheduler_service)
):
    """Manually trigger a job execution"""
    try:
        execution_id = await service.run_job_now(job_id)
        return {"job_id": job_id, "execution_id": execution_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{job_id}/history")
async def get_job_history(
    job_id: str,
    limit: int = 50,
    service=Depends(get_scheduler_service)
):
    """Get job execution history"""
    try:
        history = await service.get_job_history(job_id, limit=limit)
        return {"history": history}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
