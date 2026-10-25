"""Metrics and reliability API endpoints"""

from fastapi import APIRouter, Depends, Request
from models import MetricsReport, SLOCompliance, EventLog
from typing import List

router = APIRouter()


def get_metrics_service(request: Request):
    """Dependency to get metrics service"""
    return request.app.state.services.metrics_service


@router.get("/report", response_model=MetricsReport)
async def get_metrics_report(service=Depends(get_metrics_service)):
    """Get reliability metrics report"""
    report = await service.get_report()
    return report


@router.get("/slo", response_model=SLOCompliance)
async def get_slo_compliance(service=Depends(get_metrics_service)):
    """Get SLO compliance status"""
    compliance = await service.get_slo_compliance()
    return compliance


@router.get("/events", response_model=List[EventLog])
async def get_event_history(
    limit: int = 100,
    service=Depends(get_metrics_service)
):
    """Get event history"""
    events = await service.get_event_history(limit=limit)
    return events


@router.get("/history")
async def get_metrics_history(
    hours: int = 24,
    service=Depends(get_metrics_service)
):
    """Get metrics history over time"""
    history = await service.get_metrics_history(hours=hours)
    return history
