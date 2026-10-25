"""
Unit tests for reliability metrics.

Tests AgentMetrics, MetricsReport, MetricStorage, and ReliabilityMetrics.
"""

import pytest
from datetime import datetime, timedelta, timezone
from ia_modules.reliability.metrics import (
    AgentMetrics,
    MetricsReport,
    MemoryMetricStorage,
    ReliabilityMetrics
)


class TestAgentMetrics:
    """Test AgentMetrics dataclass."""

    def test_agent_metrics_creation(self):
        """AgentMetrics can be created."""
        metrics = AgentMetrics(
            agent_name="planner",
            total_steps=100,
            successful_steps=95,
            compensated_steps=5,
            mode_violations=3
        )

        assert metrics.agent_name == "planner"
        assert metrics.total_steps == 100
        assert metrics.successful_steps == 95

    def test_svr_calculation(self):
        """SVR is calculated correctly."""
        metrics = AgentMetrics(
            agent_name="coder",
            total_steps=100,
            successful_steps=96
        )

        assert metrics.svr == 0.96

    def test_svr_no_steps(self):
        """SVR returns 1.0 when no steps."""
        metrics = AgentMetrics(
            agent_name="empty",
            total_steps=0,
            successful_steps=0
        )

        assert metrics.svr == 1.0

    def test_cr_calculation(self):
        """CR is calculated correctly."""
        metrics = AgentMetrics(
            agent_name="coder",
            total_steps=100,
            compensated_steps=8
        )

        assert metrics.cr == 0.08

    def test_cr_no_steps(self):
        """CR returns 0.0 when no steps."""
        metrics = AgentMetrics(
            agent_name="empty",
            total_steps=0
        )

        assert metrics.cr == 0.0

    def test_ma_calculation(self):
        """MA is calculated correctly."""
        metrics = AgentMetrics(
            agent_name="executor",
            total_steps=100,
            mode_violations=5
        )

        assert metrics.ma == 0.95

    def test_ma_no_violations(self):
        """MA is 1.0 with no violations."""
        metrics = AgentMetrics(
            agent_name="perfect",
            total_steps=50,
            mode_violations=0
        )

        assert metrics.ma == 1.0


class TestMetricsReport:
    """Test MetricsReport dataclass."""

    def test_metrics_report_creation(self):
        """MetricsReport can be created."""
        report = MetricsReport(
            period_start=datetime(2025, 1, 1),
            period_end=datetime(2025, 1, 2),
            total_workflows=10,
            total_steps=100,
            svr=0.96,
            cr=0.08,
            pc=1.5,
            hir=0.03,
            ma=0.92
        )

        assert report.svr == 0.96
        assert report.total_workflows == 10

    def test_is_healthy_all_pass(self):
        """is_healthy returns True when all metrics pass."""
        report = MetricsReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            total_workflows=10,
            total_steps=100,
            svr=0.97,  # >95%
            cr=0.08,   # <10%
            pc=1.5,    # <2
            hir=0.03,  # <5%
            ma=0.92    # >90%
        )

        assert report.is_healthy() is True

    def test_is_healthy_svr_fail(self):
        """is_healthy returns False when SVR fails."""
        report = MetricsReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            total_workflows=10,
            total_steps=100,
            svr=0.94,  # ≤95% - FAIL
            cr=0.08,
            pc=1.5,
            hir=0.03,
            ma=0.92
        )

        assert report.is_healthy() is False

    def test_is_healthy_cr_fail(self):
        """is_healthy returns False when CR fails."""
        report = MetricsReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            total_workflows=10,
            total_steps=100,
            svr=0.97,
            cr=0.12,  # ≥10% - FAIL
            pc=1.5,
            hir=0.03,
            ma=0.92
        )

        assert report.is_healthy() is False

    def test_get_violations_none(self):
        """get_violations returns empty list when healthy."""
        report = MetricsReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            total_workflows=10,
            total_steps=100,
            svr=0.97,
            cr=0.08,
            pc=1.5,
            hir=0.03,
            ma=0.92
        )

        violations = report.get_violations()
        assert len(violations) == 0

    def test_get_violations_multiple(self):
        """get_violations returns all violations."""
        report = MetricsReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            total_workflows=10,
            total_steps=100,
            svr=0.94,  # FAIL
            cr=0.12,   # FAIL
            pc=2.5,    # FAIL
            hir=0.06,  # FAIL
            ma=0.88    # FAIL
        )

        violations = report.get_violations()
        assert len(violations) == 5
        assert any("SVR" in v for v in violations)
        assert any("CR" in v for v in violations)
        assert any("PC" in v for v in violations)
        assert any("HIR" in v for v in violations)
        assert any("MA" in v for v in violations)


class TestMemoryMetricStorage:
    """Test MemoryMetricStorage implementation."""

    @pytest.mark.asyncio
    async def test_record_step(self):
        """Can record step metrics."""
        storage = MemoryMetricStorage()

        await storage.record_step({
            "agent": "planner",
            "success": True
        })

        assert len(storage.steps) == 1
        assert storage.steps[0]["agent"] == "planner"
        assert "timestamp" in storage.steps[0]

    @pytest.mark.asyncio
    async def test_record_workflow(self):
        """Can record workflow metrics."""
        storage = MemoryMetricStorage()

        await storage.record_workflow({
            "workflow_id": "wf-123",
            "steps": 5,
            "retries": 1
        })

        assert len(storage.workflows) == 1
        assert storage.workflows[0]["workflow_id"] == "wf-123"

    @pytest.mark.asyncio
    async def test_get_steps_all(self):
        """Can get all steps."""
        storage = MemoryMetricStorage()

        await storage.record_step({"agent": "agent1", "success": True})
        await storage.record_step({"agent": "agent2", "success": False})

        steps = await storage.get_steps()
        assert len(steps) == 2

    @pytest.mark.asyncio
    async def test_get_steps_filtered_by_agent(self):
        """Can filter steps by agent."""
        storage = MemoryMetricStorage()

        await storage.record_step({"agent": "agent1", "success": True})
        await storage.record_step({"agent": "agent2", "success": True})
        await storage.record_step({"agent": "agent1", "success": False})

        steps = await storage.get_steps(agent="agent1")
        assert len(steps) == 2
        assert all(s["agent"] == "agent1" for s in steps)

    @pytest.mark.asyncio
    async def test_get_steps_filtered_by_time(self):
        """Can filter steps by time."""
        storage = MemoryMetricStorage()

        # Record old step
        old_step = {"agent": "agent1", "success": True}
        old_step["timestamp"] = datetime.now(timezone.utc) - timedelta(hours=2)
        storage.steps.append(old_step)

        # Record new step
        await storage.record_step({"agent": "agent2", "success": True})

        # Get steps from last hour
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        steps = await storage.get_steps(since=since)

        assert len(steps) == 1
        assert steps[0]["agent"] == "agent2"


class TestReliabilityMetrics:
    """Test ReliabilityMetrics class."""

    @pytest.mark.asyncio
    async def test_reliability_metrics_creation(self):
        """ReliabilityMetrics can be created."""
        metrics = ReliabilityMetrics()

        assert metrics.storage is not None
        assert isinstance(metrics.storage, MemoryMetricStorage)

    @pytest.mark.asyncio
    async def test_record_step(self):
        """Can record step metrics."""
        metrics = ReliabilityMetrics()

        await metrics.record_step(
            agent="coder",
            success=True,
            required_compensation=False
        )

        steps = await metrics.storage.get_steps()
        assert len(steps) == 1
        assert steps[0]["agent"] == "coder"
        assert steps[0]["success"] is True

    @pytest.mark.asyncio
    async def test_record_step_with_mode_violation(self):
        """Records mode violations correctly."""
        metrics = ReliabilityMetrics()

        await metrics.record_step(
            agent="executor",
            success=True,
            mode="explore",
            declared_mode="execute"
        )

        steps = await metrics.storage.get_steps()
        assert steps[0]["mode_violation"] is True

    @pytest.mark.asyncio
    async def test_record_workflow(self):
        """Can record workflow metrics."""
        metrics = ReliabilityMetrics()

        await metrics.record_workflow(
            workflow_id="wf-123",
            steps=10,
            retries=2,
            success=True
        )

        workflows = await metrics.storage.get_workflows()
        assert len(workflows) == 1
        assert workflows[0]["workflow_id"] == "wf-123"
        assert workflows[0]["retries"] == 2

    @pytest.mark.asyncio
    async def test_get_svr_perfect(self):
        """SVR is 1.0 when all steps succeed."""
        metrics = ReliabilityMetrics()

        await metrics.record_step("agent1", success=True)
        await metrics.record_step("agent1", success=True)
        await metrics.record_step("agent1", success=True)

        svr = await metrics.get_svr()
        assert svr == 1.0

    @pytest.mark.asyncio
    async def test_get_svr_with_failures(self):
        """SVR calculates correctly with failures."""
        metrics = ReliabilityMetrics()

        # 8 successes, 2 failures = 80% SVR
        for _ in range(8):
            await metrics.record_step("agent1", success=True)
        for _ in range(2):
            await metrics.record_step("agent1", success=False)

        svr = await metrics.get_svr()
        assert svr == 0.8

    @pytest.mark.asyncio
    async def test_get_svr_per_agent(self):
        """SVR can be calculated per agent."""
        metrics = ReliabilityMetrics()

        # Agent1: 100% success
        await metrics.record_step("agent1", success=True)
        await metrics.record_step("agent1", success=True)

        # Agent2: 50% success
        await metrics.record_step("agent2", success=True)
        await metrics.record_step("agent2", success=False)

        agent1_svr = await metrics.get_svr(agent="agent1")
        agent2_svr = await metrics.get_svr(agent="agent2")

        assert agent1_svr == 1.0
        assert agent2_svr == 0.5

    @pytest.mark.asyncio
    async def test_get_cr(self):
        """CR calculates correctly."""
        metrics = ReliabilityMetrics()

        # 2 compensated, 8 normal = 20% CR
        for _ in range(2):
            await metrics.record_step("agent1", success=True, required_compensation=True)
        for _ in range(8):
            await metrics.record_step("agent1", success=True, required_compensation=False)

        cr = await metrics.get_cr()
        assert cr == 0.2

    @pytest.mark.asyncio
    async def test_get_pc(self):
        """PC calculates correctly."""
        metrics = ReliabilityMetrics()

        # 3 workflows: 0, 1, 2 retries = avg 1.0
        await metrics.record_workflow("wf1", steps=5, retries=0, success=True)
        await metrics.record_workflow("wf2", steps=5, retries=1, success=True)
        await metrics.record_workflow("wf3", steps=5, retries=2, success=True)

        pc = await metrics.get_pc()
        assert pc == 1.0

    @pytest.mark.asyncio
    async def test_get_hir(self):
        """HIR calculates correctly."""
        metrics = ReliabilityMetrics()

        # 1 human intervention, 9 automatic = 10% HIR
        await metrics.record_workflow("wf1", steps=5, retries=0, success=True, required_human=True)
        for i in range(9):
            await metrics.record_workflow(f"wf{i+2}", steps=5, retries=0, success=True, required_human=False)

        hir = await metrics.get_hir()
        assert hir == 0.1

    @pytest.mark.asyncio
    async def test_get_ma(self):
        """MA calculates correctly."""
        metrics = ReliabilityMetrics()

        # 9 compliant, 1 violation = 90% MA
        for _ in range(9):
            await metrics.record_step("agent1", success=True, mode="execute", declared_mode="execute")
        await metrics.record_step("agent1", success=True, mode="explore", declared_mode="execute")

        ma = await metrics.get_ma()
        assert ma == 0.9

    @pytest.mark.asyncio
    async def test_get_report(self):
        """Can generate comprehensive report."""
        metrics = ReliabilityMetrics()

        # Record some data
        await metrics.record_step("agent1", success=True)
        await metrics.record_step("agent1", success=True)
        await metrics.record_workflow("wf1", steps=2, retries=0, success=True)

        report = await metrics.get_report()

        assert report.total_steps == 2
        assert report.total_workflows == 1
        assert report.svr == 1.0
        assert "agent1" in report.agent_metrics

    @pytest.mark.asyncio
    async def test_get_report_with_time_range(self):
        """Can generate report for time range."""
        metrics = ReliabilityMetrics()

        # Add old data manually
        old_step = {"agent": "agent1", "success": True}
        old_step["timestamp"] = datetime.now(timezone.utc) - timedelta(hours=2)
        metrics.storage.steps.append(old_step)

        # Add new data
        await metrics.record_step("agent2", success=False)

        # Get report from last hour
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        report = await metrics.get_report(since=since)

        # Should only include new data
        assert report.total_steps == 1
        assert "agent2" in report.agent_metrics
        assert "agent1" not in report.agent_metrics

    @pytest.mark.asyncio
    async def test_report_agent_metrics(self):
        """Report includes per-agent breakdowns."""
        metrics = ReliabilityMetrics()

        # Agent1: 100% success
        await metrics.record_step("agent1", success=True)
        await metrics.record_step("agent1", success=True)

        # Agent2: 50% success
        await metrics.record_step("agent2", success=True)
        await metrics.record_step("agent2", success=False)

        report = await metrics.get_report()

        assert len(report.agent_metrics) == 2
        assert report.agent_metrics["agent1"].svr == 1.0
        assert report.agent_metrics["agent2"].svr == 0.5
