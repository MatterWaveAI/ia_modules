"""Reliability and observability service using ia_modules library.

This service projects the real ia_modules reliability dataclasses into the
shapes the showcase_app API returns. Every field name and call shape in here
is anchored to the actual library API — see:

- ia_modules.reliability.metrics.MetricsReport (svr, cr, pc, hir, ma, tcl, wct,
  total_workflows, total_steps, agent_metrics)
- ia_modules.reliability.slo_tracker.SLOReport (mtte_*, rsr, is_compliant, ...)
- ia_modules.reliability.anomaly_detection.Anomaly (sync get_anomalies)
- ia_modules.reliability.alert_system.Alert (sync get_alerts)
- ia_modules.reliability.cost_tracker.CostReport (sync get_report)
"""

import logging
from typing import Any, Dict, List, Optional

from ia_modules.reliability import (
    AlertManager,
    AnomalyDetector,
    CircuitBreakerRegistry,
    CostTracker,
    ReliabilityMetrics,
    SLOTracker,
    SQLMetricStorage,
)

logger = logging.getLogger(__name__)


class ReliabilityService:
    """Service for reliability metrics and observability using ia_modules."""

    def __init__(self, db_manager):
        self.db_manager = db_manager

        logger.info("Initializing reliability service with ia_modules library...")

        storage = SQLMetricStorage(self.db_manager)
        self.metrics = ReliabilityMetrics(storage=storage)
        self.slo_tracker = SLOTracker()
        self.anomaly_detector = AnomalyDetector()
        self.alert_manager = AlertManager()
        self.circuit_breaker_registry = CircuitBreakerRegistry()
        self.cost_tracker = CostTracker()

        logger.info("Reliability service initialized")

    async def get_metrics(self, pipeline_id: Optional[str] = None) -> Dict[str, Any]:
        """Get reliability metrics (SVR, CR, PC, HIR, MA, TCL, WCT).

        `pipeline_id` is accepted for API compatibility but the library reports
        system-wide metrics only.
        """
        report = await self.metrics.get_report()

        return {
            "period_start": report.period_start.isoformat() if report.period_start else None,
            "period_end": report.period_end.isoformat() if report.period_end else None,
            "svr": report.svr,
            "cr": report.cr,
            "pc": report.pc,
            "hir": report.hir,
            "ma": report.ma,
            "tcl_ms": report.tcl,
            "wct_ms": report.wct,
            "total_workflows": report.total_workflows,
            "total_steps": report.total_steps,
            "healthy": report.is_healthy(),
            "violations": report.get_violations(),
            "agent_metrics": {
                name: {
                    "agent_name": m.agent_name,
                    "total_steps": m.total_steps,
                    "successful_steps": m.successful_steps,
                    "compensated_steps": m.compensated_steps,
                    "mode_violations": m.mode_violations,
                    "svr": m.svr,
                    "cr": m.cr,
                    "ma": m.ma,
                }
                for name, m in report.agent_metrics.items()
            },
        }

    async def get_slo_status(self, pipeline_id: Optional[str] = None) -> Dict[str, Any]:
        """Get SLO compliance status (MTTE and RSR)."""
        slo = await self.slo_tracker.get_report()

        return {
            "period_start": slo.period_start.isoformat() if slo.period_start else None,
            "period_end": slo.period_end.isoformat() if slo.period_end else None,
            "mtte": {
                "avg_ms": slo.mtte_avg_ms,
                "p50_ms": slo.mtte_p50_ms,
                "p95_ms": slo.mtte_p95_ms,
                "p99_ms": slo.mtte_p99_ms,
                "target_ms": slo.mtte_target_ms,
                "total_measurements": slo.total_mtte_measurements,
                "compliant": slo.is_mtte_compliant(),
            },
            "rsr": {
                "value": slo.rsr,
                "target": slo.rsr_target,
                "total_attempts": slo.total_rsr_attempts,
                "successful_replays": slo.successful_replays,
                "compliant": slo.is_rsr_compliant(),
            },
            "compliant": slo.is_compliant(),
            "violations": slo.get_violations(),
        }

    async def get_anomalies(
        self,
        pipeline_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get detected anomalies. `get_anomalies` on the library is sync."""
        anomalies = self.anomaly_detector.get_anomalies()
        # Library has no built-in limit param; slice here.
        return [_anomaly_to_dict(a) for a in anomalies[:limit]]

    async def get_alerts(
        self,
        pipeline_id: Optional[str] = None,
        active_only: bool = True,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """Get alerts. `get_alerts` on the library is sync.

        `active_only` is mapped to the library's `acknowledged` filter
        (active = not acknowledged).
        """
        acknowledged_filter = False if active_only else None
        alerts = self.alert_manager.get_alerts(acknowledged=acknowledged_filter)
        return [_alert_to_dict(a) for a in alerts[:limit]]

    async def get_circuit_breaker_status(self) -> Dict[str, Any]:
        """Get circuit breaker status for all registered breakers."""
        return {
            "circuit_breakers": self.circuit_breaker_registry.get_all_metrics(),
        }

    async def get_cost_metrics(self, pipeline_id: Optional[str] = None) -> Dict[str, Any]:
        """Get cost tracking metrics. `get_report` on CostTracker is sync."""
        report = self.cost_tracker.get_report()

        return {
            "period_start": report.period_start.isoformat() if report.period_start else None,
            "period_end": report.period_end.isoformat() if report.period_end else None,
            "total_cost": report.total_cost,
            "total_workflows": report.total_workflows,
            "cost_per_workflow": report.cost_per_workflow,
            "tokens_per_workflow": report.tokens_per_workflow,
            "by_category": report.by_category,
            "by_agent": report.by_agent,
        }

    async def get_trend_analysis(
        self,
        metric_name: str,
        pipeline_id: Optional[str] = None,
        window_size: int = 10,
    ) -> Dict[str, Any]:
        """Get trend analysis for a specific metric.

        The TrendAnalyzer in the library operates on raw value lists, not
        named metrics over time — we don't have a stream hooked up yet, so
        this returns a stable placeholder response that matches the shape
        the frontend expects.
        """
        return {
            "metric_name": metric_name,
            "pipeline_id": pipeline_id,
            "window_size": window_size,
            "trend_direction": "stable",
            "slope": 0.0,
            "confidence": 0.0,
            "prediction": None,
        }


# -------- helpers --------


def _enum_value(v: Any) -> Any:
    """Extract `.value` from Enum-like objects, otherwise pass through."""
    return getattr(v, "value", v)


def _anomaly_to_dict(a: Any) -> Dict[str, Any]:
    return {
        "type": _enum_value(a.type),
        "severity": _enum_value(a.severity),
        "metric_name": a.metric_name,
        "current_value": a.current_value,
        "expected_value": a.expected_value,
        "deviation": a.deviation,
        "timestamp": a.timestamp.isoformat() if hasattr(a.timestamp, "isoformat") else a.timestamp,
        "agent": getattr(a, "agent", None),
        "context": getattr(a, "context", {}) or {},
    }


def _alert_to_dict(a: Any) -> Dict[str, Any]:
    return {
        "type": _enum_value(a.type),
        "severity": _enum_value(a.severity),
        "title": a.title,
        "message": a.message,
        "source": a.source,
        "timestamp": a.timestamp.isoformat() if hasattr(a.timestamp, "isoformat") else a.timestamp,
        "acknowledged": a.acknowledged,
        "acknowledged_at": a.acknowledged_at.isoformat() if a.acknowledged_at else None,
        "acknowledged_by": a.acknowledged_by,
        "context": getattr(a, "context", {}) or {},
    }
