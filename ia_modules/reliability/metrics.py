"""
Reliability Metrics

Tracks agent performance metrics (SVR, CR, PC, HIR, MA) for production monitoring.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timezone
import logging


@dataclass
class AgentMetrics:
    """Per-agent metric breakdown."""
    agent_name: str
    total_steps: int = 0
    successful_steps: int = 0
    compensated_steps: int = 0
    mode_violations: int = 0

    @property
    def svr(self) -> float:
        """Step Validity Rate for this agent."""
        if self.total_steps == 0:
            return 1.0
        return self.successful_steps / self.total_steps

    @property
    def cr(self) -> float:
        """Compensation Rate for this agent."""
        if self.total_steps == 0:
            return 0.0
        return self.compensated_steps / self.total_steps

    @property
    def ma(self) -> float:
        """Mode Adherence for this agent."""
        if self.total_steps == 0:
            return 1.0
        mode_compliant = self.total_steps - self.mode_violations
        return mode_compliant / self.total_steps


@dataclass
class MetricsReport:
    """
    Comprehensive metrics summary.

    Provides system-wide and per-agent reliability metrics.
    """
    period_start: datetime
    period_end: datetime
    total_workflows: int
    total_steps: int

    # System-wide metrics
    svr: float  # Step Validity Rate - Target: >95%
    cr: float   # Compensation Rate - Target: <10%
    pc: float   # Plan Churn - Target: <2
    hir: float  # Human Intervention Rate - Target: <5%
    ma: float   # Mode Adherence - Target: >90%

    # Per-agent breakdown
    agent_metrics: Dict[str, AgentMetrics] = field(default_factory=dict)

    # Trends (time series)
    svr_trend: List[Tuple[datetime, float]] = field(default_factory=list)

    # FinOps Performance metrics (optional, set when available)
    tcl: Optional[float] = None  # Tool Call Latency (ms) - Average duration
    wct: Optional[float] = None  # Workflow Completion Time (ms) - Average duration

    def is_healthy(self) -> bool:
        """Check if all metrics meet targets."""
        return (
            self.svr > 0.95 and
            self.cr < 0.10 and
            self.pc < 2.0 and
            self.hir < 0.05 and
            self.ma > 0.90
        )

    def get_violations(self) -> List[str]:
        """Get list of metric violations."""
        violations = []

        if self.svr <= 0.95:
            violations.append(f"SVR too low: {self.svr:.2%} (target >95%)")
        if self.cr >= 0.10:
            violations.append(f"CR too high: {self.cr:.2%} (target <10%)")
        if self.pc >= 2.0:
            violations.append(f"PC too high: {self.pc:.1f} (target <2)")
        if self.hir >= 0.05:
            violations.append(f"HIR too high: {self.hir:.2%} (target <5%)")
        if self.ma <= 0.90:
            violations.append(f"MA too low: {self.ma:.2%} (target >90%)")

        return violations


class MetricStorage:
    """Abstract storage interface for metrics."""

    async def record_step(self, record: Dict[str, Any]):
        """Record a step metric."""
        raise NotImplementedError

    async def record_workflow(self, record: Dict[str, Any]):
        """Record a workflow metric."""
        raise NotImplementedError

    async def get_steps(
        self,
        agent: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get step records."""
        raise NotImplementedError

    async def get_workflows(
        self,
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get workflow records."""
        raise NotImplementedError


class MemoryMetricStorage(MetricStorage):
    """In-memory metric storage for testing."""

    def __init__(self):
        self.steps: List[Dict[str, Any]] = []
        self.workflows: List[Dict[str, Any]] = []

    async def record_step(self, record: Dict[str, Any]):
        """Record a step metric."""
        record["timestamp"] = datetime.now(timezone.utc)
        self.steps.append(record)

    async def record_workflow(self, record: Dict[str, Any]):
        """Record a workflow metric."""
        record["timestamp"] = datetime.now(timezone.utc)
        self.workflows.append(record)

    async def get_steps(
        self,
        agent: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get step records with filtering."""
        results = self.steps

        if agent:
            results = [s for s in results if s.get("agent") == agent]

        if since:
            results = [s for s in results if s.get("timestamp", datetime.min) >= since]

        return results

    async def get_workflows(
        self,
        since: Optional[datetime] = None
    ) -> List[Dict[str, Any]]:
        """Get workflow records with filtering."""
        results = self.workflows

        if since:
            results = [w for w in results if w.get("timestamp", datetime.min) >= since]

        return results


class ReliabilityMetrics:
    """
    Track agent reliability metrics.

    Provides five core metrics for production monitoring:
    - SVR (Step Validity Rate): % of steps that succeed
    - CR (Compensation Rate): % of steps requiring rollback
    - PC (Plan Churn): Average retries per workflow
    - HIR (Human Intervention Rate): % of workflows requiring human approval
    - MA (Mode Adherence): % of steps following declared mode

    Example:
        >>> metrics = ReliabilityMetrics()
        >>>
        >>> # Record step
        >>> await metrics.record_step(
        ...     agent="planner",
        ...     success=True,
        ...     required_compensation=False
        ... )
        >>>
        >>> # Get metrics
        >>> report = await metrics.get_report()
        >>> print(f"SVR: {report.svr:.2%}")
        >>> print(f"System healthy: {report.is_healthy()}")
    """

    def __init__(self, storage: Optional[MetricStorage] = None):
        """
        Initialize metrics tracker.

        Args:
            storage: Metric storage backend (defaults to MemoryMetricStorage)
        """
        self.storage = storage or MemoryMetricStorage()
        self.logger = logging.getLogger("ReliabilityMetrics")

    async def record_step(
        self,
        agent: str,
        success: bool,
        required_compensation: bool = False,
        required_human: bool = False,
        mode: Optional[str] = None,
        declared_mode: Optional[str] = None
    ):
        """
        Record individual step metrics.

        Args:
            agent: Agent name
            success: Whether step succeeded
            required_compensation: Whether step needed rollback/undo
            required_human: Whether step needed human intervention
            mode: Actual mode used
            declared_mode: Agent's declared mode

        Example:
            >>> await metrics.record_step(
            ...     agent="coder",
            ...     success=True,
            ...     required_compensation=False,
            ...     mode="execute",
            ...     declared_mode="execute"
            ... )
        """
        mode_violation = False
        if mode and declared_mode:
            mode_violation = mode != declared_mode

        await self.storage.record_step({
            "agent": agent,
            "success": success,
            "required_compensation": required_compensation,
            "required_human": required_human,
            "mode": mode,
            "declared_mode": declared_mode,
            "mode_violation": mode_violation
        })

        self.logger.debug(f"Recorded step for {agent}: success={success}")

    async def record_workflow(
        self,
        workflow_id: str,
        steps: int,
        retries: int,
        success: bool,
        required_human: bool = False
    ):
        """
        Record complete workflow metrics.

        Args:
            workflow_id: Workflow identifier
            steps: Total steps executed
            retries: Number of retries needed
            success: Whether workflow succeeded
            required_human: Whether human intervention was needed

        Example:
            >>> await metrics.record_workflow(
            ...     workflow_id="workflow-123",
            ...     steps=5,
            ...     retries=1,
            ...     success=True,
            ...     required_human=False
            ... )
        """
        await self.storage.record_workflow({
            "workflow_id": workflow_id,
            "steps": steps,
            "retries": retries,
            "success": success,
            "required_human": required_human
        })

        self.logger.debug(f"Recorded workflow {workflow_id}: {steps} steps, {retries} retries")

    async def get_svr(
        self,
        agent: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> float:
        """
        Get Step Validity Rate.

        SVR = successful_steps / total_steps
        Target: >95%

        Args:
            agent: Filter by agent (None for all)
            since: Only include steps since this time

        Returns:
            SVR as float (0.0 - 1.0)
        """
        steps = await self.storage.get_steps(agent=agent, since=since)

        if not steps:
            return 1.0  # No data = assume perfect

        successful = sum(1 for s in steps if s.get("success"))
        return successful / len(steps)

    async def get_cr(
        self,
        agent: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> float:
        """
        Get Compensation Rate.

        CR = compensated_steps / total_steps
        Target: <10%

        Args:
            agent: Filter by agent (None for all)
            since: Only include steps since this time

        Returns:
            CR as float (0.0 - 1.0)
        """
        steps = await self.storage.get_steps(agent=agent, since=since)

        if not steps:
            return 0.0

        compensated = sum(1 for s in steps if s.get("required_compensation"))
        return compensated / len(steps)

    async def get_pc(
        self,
        since: Optional[datetime] = None
    ) -> float:
        """
        Get Plan Churn.

        PC = total_retries / total_workflows
        Target: <2.0

        Args:
            since: Only include workflows since this time

        Returns:
            PC as float (average retries per workflow)
        """
        workflows = await self.storage.get_workflows(since=since)

        if not workflows:
            return 0.0

        total_retries = sum(w.get("retries", 0) for w in workflows)
        return total_retries / len(workflows)

    async def get_hir(
        self,
        since: Optional[datetime] = None
    ) -> float:
        """
        Get Human Intervention Rate.

        HIR = human_approved_workflows / total_workflows
        Target: <5%

        Args:
            since: Only include workflows since this time

        Returns:
            HIR as float (0.0 - 1.0)
        """
        workflows = await self.storage.get_workflows(since=since)

        if not workflows:
            return 0.0

        required_human = sum(1 for w in workflows if w.get("required_human"))
        return required_human / len(workflows)

    async def get_ma(
        self,
        agent: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> float:
        """
        Get Mode Adherence.

        MA = mode_compliant_steps / total_steps
        Target: >90%

        Args:
            agent: Filter by agent (None for all)
            since: Only include steps since this time

        Returns:
            MA as float (0.0 - 1.0)
        """
        steps = await self.storage.get_steps(agent=agent, since=since)

        if not steps:
            return 1.0

        violations = sum(1 for s in steps if s.get("mode_violation"))
        compliant = len(steps) - violations
        return compliant / len(steps)

    async def get_report(
        self,
        since: Optional[datetime] = None
    ) -> MetricsReport:
        """
        Get comprehensive metrics report.

        Args:
            since: Only include data since this time (None for all time)

        Returns:
            MetricsReport with all metrics

        Example:
            >>> report = await metrics.get_report()
            >>> print(f"SVR: {report.svr:.2%}")
            >>> print(f"Healthy: {report.is_healthy()}")
            >>> for violation in report.get_violations():
            ...     print(f"  - {violation}")
        """
        # Determine time period
        period_start = since or datetime.min
        period_end = datetime.now(timezone.utc)

        # Get all data
        steps = await self.storage.get_steps(since=since)
        workflows = await self.storage.get_workflows(since=since)

        # Calculate system-wide metrics
        svr = await self.get_svr(since=since)
        cr = await self.get_cr(since=since)
        pc = await self.get_pc(since=since)
        hir = await self.get_hir(since=since)
        ma = await self.get_ma(since=since)

        # Calculate per-agent metrics
        agent_metrics: Dict[str, AgentMetrics] = {}
        agent_names = set(s.get("agent") for s in steps)

        for agent in agent_names:
            if agent is None:
                continue
            agent_steps = [s for s in steps if s.get("agent") == agent]

            agent_metrics[agent] = AgentMetrics(
                agent_name=agent,
                total_steps=len(agent_steps),
                successful_steps=sum(1 for s in agent_steps if s.get("success")),
                compensated_steps=sum(1 for s in agent_steps if s.get("required_compensation")),
                mode_violations=sum(1 for s in agent_steps if s.get("mode_violation"))
            )

        # Calculate TCL (Tool Call Latency) if tool timing data available
        tcl = None
        tool_durations = [
            s.get("tool_duration_ms")
            for s in steps
            if s.get("tool_duration_ms") is not None
        ]
        if tool_durations:
            tcl = sum(tool_durations) / len(tool_durations)

        # Calculate WCT (Workflow Completion Time) if workflow timing data available
        wct = None
        workflow_durations = [
            w.get("duration_ms")
            for w in workflows
            if w.get("duration_ms") is not None
        ]
        if workflow_durations:
            wct = sum(workflow_durations) / len(workflow_durations)

        return MetricsReport(
            period_start=period_start,
            period_end=period_end,
            total_workflows=len(workflows),
            total_steps=len(steps),
            svr=svr,
            cr=cr,
            pc=pc,
            hir=hir,
            ma=ma,
            agent_metrics=agent_metrics,
            tcl=tcl,
            wct=wct
        )
