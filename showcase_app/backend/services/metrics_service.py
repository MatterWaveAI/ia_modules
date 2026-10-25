"""Metrics service for reliability tracking"""

import sys
import os
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..')))

from ia_modules.reliability.metrics import ReliabilityMetrics
from ia_modules.reliability.sql_metric_storage import SQLMetricStorage
from datetime import datetime, timezone
from typing import Optional, List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class MetricsService:
    """Service for managing reliability metrics"""

    def __init__(self, db_manager):
        self.db_manager = db_manager

        logger.info("Initializing metrics service...")

        # Use SQL storage with database
        self.storage = SQLMetricStorage(self.db_manager)
        self.metrics = ReliabilityMetrics(self.storage)

        # Extended metrics tracking
        self.error_times: List[datetime] = []
        self.retry_attempts: List[Dict[str, Any]] = []
        self.token_counts: List[int] = []
        self.workflow_costs: List[float] = []
        self.explanations: List[Dict[str, Any]] = []

        logger.info("Metrics service initialized")

    async def cleanup(self):
        """Cleanup metrics service"""
        pass

    async def record_step(
        self,
        agent: str,
        success: bool,
        required_compensation: bool = False,
        required_human: bool = False,
        mode: Optional[str] = None,
        declared_mode: Optional[str] = None
    ):
        """Record step execution"""
        try:
            await self.metrics.record_step(
                agent=agent,
                success=success,
                required_compensation=required_compensation,
                required_human=required_human,
                mode=mode,
                declared_mode=declared_mode
            )

            # Track errors for MTTE calculation
            if not success:
                self.error_times.append(datetime.now(timezone.utc))
        except Exception as e:
            logger.error(f"Error recording step metrics for agent {agent}: {e}", exc_info=True)

    async def record_workflow(
        self,
        workflow_id: str,
        steps: int,
        retries: int,
        success: bool,
        required_human: bool = False,
        tokens: Optional[int] = None,
        cost: Optional[float] = None
    ):
        """Record workflow execution"""
        try:
            await self.metrics.record_workflow(
                workflow_id=workflow_id,
                steps=steps,
                retries=retries,
                success=success,
                required_human=required_human
            )

            # Track retry success for RSR
            if retries > 0:
                self.retry_attempts.append({
                    "workflow_id": workflow_id,
                    "retries": retries,
                    "success": success,
                    "timestamp": datetime.now(timezone.utc)
                })

            # Track tokens and cost for TPW and CPSW
            if tokens:
                self.token_counts.append(tokens)
            if cost and success:
                self.workflow_costs.append(cost)
        except Exception as e:
            logger.error(f"Error recording workflow metrics for workflow {workflow_id}: {e}", exc_info=True)

    async def get_report(self) -> Dict[str, Any]:
        """Get reliability metrics report"""
        report = await self.metrics.get_report()

        # Calculate additional metrics
        ma = self._calculate_ma()
        mtte = self._calculate_mtte()
        rsr = self._calculate_rsr()
        eqs = self._calculate_eqs()
        tpw = self._calculate_tpw()
        cpsw = self._calculate_cpsw()

        return {
            "svr": report.svr,
            "cr": report.cr,
            "pc": report.pc,
            "hir": report.hir,
            "ma": ma,
            "tcl": report.tcl,
            "wct": report.wct,
            "mtte": mtte,
            "rsr": rsr,
            "eqs": eqs,
            "tpw": tpw,
            "cpsw": cpsw,
            "total_workflows": report.total_workflows,
            "total_steps": report.total_steps,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    def _calculate_ma(self) -> Optional[float]:
        """Calculate Model Accuracy - % of steps where agent made correct decision"""
        return None

    def _calculate_mtte(self) -> Optional[float]:
        """Calculate Mean Time To Error - average time between failures in hours"""
        intervals = [
            (self.error_times[i] - self.error_times[i-1]).total_seconds() / 3600
            for i in range(1, len(self.error_times))
        ]
        return round(sum(intervals) / len(intervals), 2) if intervals else None

    def _calculate_rsr(self) -> Optional[float]:
        """Calculate Retry Success Rate - % of workflows that succeed after retry"""
        successful_retries = sum(1 for r in self.retry_attempts if r["success"])
        return round(successful_retries / len(self.retry_attempts), 3) if self.retry_attempts else None

    def _calculate_eqs(self) -> Optional[float]:
        """Calculate Explanation Quality Score - quality of agent explanations"""
        scores = [e.get("score", 0.8) for e in self.explanations]
        return round(sum(scores) / len(scores), 3) if scores else None

    def _calculate_tpw(self) -> Optional[float]:
        """Calculate Tokens Per Workflow - average tokens consumed"""
        return round(sum(self.token_counts) / len(self.token_counts), 0) if self.token_counts else None

    def _calculate_cpsw(self) -> Optional[float]:
        """Calculate Cost Per Successful Workflow - average cost in USD"""
        return round(sum(self.workflow_costs) / len(self.workflow_costs), 3) if self.workflow_costs else None

    async def get_slo_compliance(self) -> Dict[str, Any]:
        """Get SLO compliance status"""
        # Get current metrics
        report = await self.get_report()

        # Simple SLO compliance based on metrics
        svr_target = 0.95
        cr_target = 0.90
        hir_target = 0.05
        ma_target = 0.85

        svr_compliant = report["svr"] >= svr_target if report["svr"] is not None else True
        cr_compliant = report["cr"] >= cr_target if report["cr"] is not None else True
        hir_compliant = report["hir"] <= hir_target if report["hir"] is not None else True
        ma_compliant = report["ma"] >= ma_target if report["ma"] is not None else True

        return {
            "svr_compliant": svr_compliant,
            "svr_current": report["svr"],
            "svr_target": svr_target,
            "cr_compliant": cr_compliant,
            "cr_current": report["cr"],
            "cr_target": cr_target,
            "hir_compliant": hir_compliant,
            "hir_current": report["hir"],
            "hir_target": hir_target,
            "ma_compliant": ma_compliant,
            "ma_current": report["ma"],
            "ma_target": ma_target,
            "overall_compliant": svr_compliant and cr_compliant and hir_compliant and ma_compliant,
            "timestamp": datetime.now(timezone.utc).isoformat()
        }

    async def get_event_history(self, limit: int = 100) -> List[Dict[str, Any]]:
        """Get event history"""
        steps = await self.storage.get_steps()
        workflows = await self.storage.get_workflows()

        events = []

        # Add step events
        for step in steps[-limit:]:
            events.append({
                "id": str(hash(f"{step['agent']}-{step['timestamp']}")),
                "event_type": "step_execution",
                "agent_name": step["agent"],
                "success": step["success"],
                "timestamp": step["timestamp"].isoformat() if isinstance(step["timestamp"], datetime) else step["timestamp"],
                "data": {
                    "required_compensation": step.get("required_compensation", False),
                    "required_human": step.get("required_human", False),
                }
            })

        # Add workflow events
        for workflow in workflows[-limit:]:
            events.append({
                "id": workflow["workflow_id"],
                "event_type": "workflow_execution",
                "agent_name": workflow.get("agent", "system"),
                "success": workflow["success"],
                "timestamp": workflow["timestamp"].isoformat() if isinstance(workflow["timestamp"], datetime) else workflow["timestamp"],
                "data": {
                    "steps": workflow["steps"],
                    "retries": workflow["retries"],
                    "required_human": workflow.get("required_human", False),
                }
            })

        # Sort by timestamp
        events.sort(key=lambda e: e["timestamp"], reverse=True)
        return events[:limit]

    async def get_metrics_history(self, hours: int = 24) -> Dict[str, Any]:
        """Get metrics history over time"""
        # For demo, return current metrics
        # In production, this would query time-series data
        report = await self.get_report()

        return {
            "period": f"last_{hours}_hours",
            "datapoints": [report],  # In production, multiple datapoints
            "summary": report
        }
