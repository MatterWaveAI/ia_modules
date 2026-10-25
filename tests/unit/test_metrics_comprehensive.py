"""Comprehensive tests for reliability.metrics module"""

import pytest
from datetime import datetime, timezone, timedelta
from ia_modules.reliability.metrics import (
    AgentMetrics,
    MetricsReport,
    MemoryMetricStorage,
    ReliabilityMetrics
)


class TestAgentMetrics:
    """Test AgentMetrics dataclass"""

    def test_init(self):
        """Test metric initialization"""
        metrics = AgentMetrics(agent_name="planner")
        assert metrics.agent_name == "planner"
        assert metrics.total_steps == 0
        assert metrics.successful_steps == 0
        assert metrics.compensated_steps == 0
        assert metrics.mode_violations == 0

    def test_svr_zero_steps(self):
        """Test SVR with zero steps"""
        metrics = AgentMetrics(agent_name="test")
        assert metrics.svr == 1.0

    def test_svr_calculation(self):
        """Test SVR calculation"""
        metrics = AgentMetrics(
            agent_name="test",
            total_steps=10,
            successful_steps=9
        )
        assert metrics.svr == 0.9

    def test_cr_zero_steps(self):
        """Test CR with zero steps"""
        metrics = AgentMetrics(agent_name="test")
        assert metrics.cr == 0.0

    def test_cr_calculation(self):
        """Test CR calculation"""
        metrics = AgentMetrics(
            agent_name="test",
            total_steps=10,
            compensated_steps=2
        )
        assert metrics.cr == 0.2

    def test_ma_zero_steps(self):
        """Test MA with zero steps"""
        metrics = AgentMetrics(agent_name="test")
        assert metrics.ma == 1.0

    def test_ma_calculation(self):
        """Test MA calculation"""
        metrics = AgentMetrics(
            agent_name="test",
            total_steps=10,
            mode_violations=1
        )
        assert metrics.ma == 0.9


class TestMetricsReport:
    """Test MetricsReport dataclass"""

    def test_init(self):
        """Test report initialization"""
        start = datetime.now(timezone.utc)
        end = start + timedelta(hours=1)

        report = MetricsReport(
            period_start=start,
            period_end=end,
            total_workflows=100,
            total_steps=500,
            svr=0.96,
            cr=0.08,
            pc=1.5,
            hir=0.04,
            ma=0.92
        )

        assert report.total_workflows == 100
        assert report.total_steps == 500
        assert report.svr == 0.96

    def test_is_healthy_all_pass(self):
        """Test healthy system"""
        report = MetricsReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            total_workflows=100,
            total_steps=500,
            svr=0.96,
            cr=0.08,
            pc=1.5,
            hir=0.04,
            ma=0.92
        )

        assert report.is_healthy() is True

    def test_is_healthy_svr_violation(self):
        """Test unhealthy due to low SVR"""
        report = MetricsReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            total_workflows=100,
            total_steps=500,
            svr=0.94,
            cr=0.08,
            pc=1.5,
            hir=0.04,
            ma=0.92
        )

        assert report.is_healthy() is False

    def test_get_violations_empty(self):
        """Test no violations"""
        report = MetricsReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            total_workflows=100,
            total_steps=500,
            svr=0.96,
            cr=0.08,
            pc=1.5,
            hir=0.04,
            ma=0.92
        )

        violations = report.get_violations()
        assert len(violations) == 0

    def test_get_violations_all(self):
        """Test all violations"""
        report = MetricsReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            total_workflows=100,
            total_steps=500,
            svr=0.94,
            cr=0.11,
            pc=2.5,
            hir=0.06,
            ma=0.88
        )

        violations = report.get_violations()
        assert len(violations) == 5
        assert any("SVR" in v for v in violations)
        assert any("CR" in v for v in violations)
        assert any("PC" in v for v in violations)
        assert any("HIR" in v for v in violations)
        assert any("MA" in v for v in violations)

    def test_optional_finops_metrics(self):
        """Test optional TCL and WCT metrics"""
        report = MetricsReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            total_workflows=100,
            total_steps=500,
            svr=0.96,
            cr=0.08,
            pc=1.5,
            hir=0.04,
            ma=0.92,
            tcl=150.5,
            wct=3000.0
        )

        assert report.tcl == 150.5
        assert report.wct == 3000.0


class TestMemoryMetricStorage:
    """Test MemoryMetricStorage"""

    @pytest.mark.asyncio
    async def test_init(self):
        """Test storage initialization"""
        storage = MemoryMetricStorage()
        assert len(storage.steps) == 0
        assert len(storage.workflows) == 0

    @pytest.mark.asyncio
    async def test_record_step(self):
        """Test recording step"""
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
        """Test recording workflow"""
        storage = MemoryMetricStorage()

        await storage.record_workflow({
            "workflow_id": "wf-123",
            "steps": 5
        })

        assert len(storage.workflows) == 1
        assert storage.workflows[0]["workflow_id"] == "wf-123"
        assert "timestamp" in storage.workflows[0]

    @pytest.mark.asyncio
    async def test_get_steps_all(self):
        """Test getting all steps"""
        storage = MemoryMetricStorage()

        await storage.record_step({"agent": "planner", "success": True})
        await storage.record_step({"agent": "coder", "success": False})

        steps = await storage.get_steps()
        assert len(steps) == 2

    @pytest.mark.asyncio
    async def test_get_steps_filter_by_agent(self):
        """Test filtering steps by agent"""
        storage = MemoryMetricStorage()

        await storage.record_step({"agent": "planner", "success": True})
        await storage.record_step({"agent": "coder", "success": False})
        await storage.record_step({"agent": "planner", "success": True})

        steps = await storage.get_steps(agent="planner")
        assert len(steps) == 2
        assert all(s["agent"] == "planner" for s in steps)

    @pytest.mark.asyncio
    async def test_get_steps_filter_by_time(self):
        """Test filtering steps by time"""
        storage = MemoryMetricStorage()

        await storage.record_step({"agent": "planner", "success": True})

        # Record with future timestamp
        future = datetime.now(timezone.utc) + timedelta(hours=1)
        steps = await storage.get_steps(since=future)

        assert len(steps) == 0

    @pytest.mark.asyncio
    async def test_get_workflows_all(self):
        """Test getting all workflows"""
        storage = MemoryMetricStorage()

        await storage.record_workflow({"workflow_id": "wf-1"})
        await storage.record_workflow({"workflow_id": "wf-2"})

        workflows = await storage.get_workflows()
        assert len(workflows) == 2

    @pytest.mark.asyncio
    async def test_get_workflows_filter_by_time(self):
        """Test filtering workflows by time"""
        storage = MemoryMetricStorage()

        await storage.record_workflow({"workflow_id": "wf-1"})

        future = datetime.now(timezone.utc) + timedelta(hours=1)
        workflows = await storage.get_workflows(since=future)

        assert len(workflows) == 0


class TestReliabilityMetrics:
    """Test ReliabilityMetrics class"""

    @pytest.mark.asyncio
    async def test_init_default_storage(self):
        """Test initialization with default storage"""
        metrics = ReliabilityMetrics()
        assert metrics.storage is not None
        assert isinstance(metrics.storage, MemoryMetricStorage)

    @pytest.mark.asyncio
    async def test_init_custom_storage(self):
        """Test initialization with custom storage"""
        custom_storage = MemoryMetricStorage()
        metrics = ReliabilityMetrics(storage=custom_storage)
        assert metrics.storage is custom_storage

    @pytest.mark.asyncio
    async def test_record_step_basic(self):
        """Test recording basic step"""
        metrics = ReliabilityMetrics()

        await metrics.record_step(
            agent="planner",
            success=True
        )

        steps = await metrics.storage.get_steps()
        assert len(steps) == 1
        assert steps[0]["agent"] == "planner"
        assert steps[0]["success"] is True

    @pytest.mark.asyncio
    async def test_record_step_with_compensation(self):
        """Test recording step with compensation"""
        metrics = ReliabilityMetrics()

        await metrics.record_step(
            agent="coder",
            success=False,
            required_compensation=True
        )

        steps = await metrics.storage.get_steps()
        assert steps[0]["required_compensation"] is True

    @pytest.mark.asyncio
    async def test_record_step_mode_violation(self):
        """Test recording step with mode violation"""
        metrics = ReliabilityMetrics()

        await metrics.record_step(
            agent="planner",
            success=True,
            mode="execute",
            declared_mode="explore"
        )

        steps = await metrics.storage.get_steps()
        assert steps[0]["mode_violation"] is True

    @pytest.mark.asyncio
    async def test_record_step_mode_match(self):
        """Test recording step with matching mode"""
        metrics = ReliabilityMetrics()

        await metrics.record_step(
            agent="planner",
            success=True,
            mode="explore",
            declared_mode="explore"
        )

        steps = await metrics.storage.get_steps()
        assert steps[0]["mode_violation"] is False

    @pytest.mark.asyncio
    async def test_record_workflow(self):
        """Test recording workflow"""
        metrics = ReliabilityMetrics()

        await metrics.record_workflow(
            workflow_id="wf-123",
            steps=5,
            retries=1,
            success=True
        )

        workflows = await metrics.storage.get_workflows()
        assert len(workflows) == 1
        assert workflows[0]["workflow_id"] == "wf-123"
        assert workflows[0]["steps"] == 5
        assert workflows[0]["retries"] == 1

    @pytest.mark.asyncio
    async def test_get_svr_no_data(self):
        """Test SVR with no data"""
        metrics = ReliabilityMetrics()
        svr = await metrics.get_svr()
        assert svr == 1.0

    @pytest.mark.asyncio
    async def test_get_svr_calculation(self):
        """Test SVR calculation"""
        metrics = ReliabilityMetrics()

        await metrics.record_step("planner", success=True)
        await metrics.record_step("planner", success=True)
        await metrics.record_step("planner", success=False)

        svr = await metrics.get_svr()
        assert svr == 2.0 / 3.0

    @pytest.mark.asyncio
    async def test_get_svr_by_agent(self):
        """Test SVR filtered by agent"""
        metrics = ReliabilityMetrics()

        await metrics.record_step("planner", success=True)
        await metrics.record_step("coder", success=False)

        svr = await metrics.get_svr(agent="planner")
        assert svr == 1.0

    @pytest.mark.asyncio
    async def test_get_cr_no_data(self):
        """Test CR with no data"""
        metrics = ReliabilityMetrics()
        cr = await metrics.get_cr()
        assert cr == 0.0

    @pytest.mark.asyncio
    async def test_get_cr_calculation(self):
        """Test CR calculation"""
        metrics = ReliabilityMetrics()

        await metrics.record_step("planner", success=True, required_compensation=True)
        await metrics.record_step("planner", success=True, required_compensation=False)
        await metrics.record_step("planner", success=True, required_compensation=False)

        cr = await metrics.get_cr()
        assert cr == 1.0 / 3.0

    @pytest.mark.asyncio
    async def test_get_pc_no_data(self):
        """Test PC with no data"""
        metrics = ReliabilityMetrics()
        pc = await metrics.get_pc()
        assert pc == 0.0

    @pytest.mark.asyncio
    async def test_get_pc_calculation(self):
        """Test PC calculation"""
        metrics = ReliabilityMetrics()

        await metrics.record_workflow("wf-1", steps=5, retries=2, success=True)
        await metrics.record_workflow("wf-2", steps=3, retries=0, success=True)
        await metrics.record_workflow("wf-3", steps=4, retries=1, success=True)

        pc = await metrics.get_pc()
        assert pc == 1.0

    @pytest.mark.asyncio
    async def test_get_hir_no_data(self):
        """Test HIR with no data"""
        metrics = ReliabilityMetrics()
        hir = await metrics.get_hir()
        assert hir == 0.0

    @pytest.mark.asyncio
    async def test_get_hir_calculation(self):
        """Test HIR calculation"""
        metrics = ReliabilityMetrics()

        await metrics.record_workflow("wf-1", steps=5, retries=0, success=True, required_human=True)
        await metrics.record_workflow("wf-2", steps=3, retries=0, success=True, required_human=False)
        await metrics.record_workflow("wf-3", steps=4, retries=0, success=True, required_human=False)

        hir = await metrics.get_hir()
        assert hir == 1.0 / 3.0

    @pytest.mark.asyncio
    async def test_get_ma_no_data(self):
        """Test MA with no data"""
        metrics = ReliabilityMetrics()
        ma = await metrics.get_ma()
        assert ma == 1.0

    @pytest.mark.asyncio
    async def test_get_ma_calculation(self):
        """Test MA calculation"""
        metrics = ReliabilityMetrics()

        await metrics.record_step("planner", success=True, mode="explore", declared_mode="explore")
        await metrics.record_step("planner", success=True, mode="execute", declared_mode="explore")
        await metrics.record_step("planner", success=True, mode="explore", declared_mode="explore")

        ma = await metrics.get_ma()
        assert ma == 2.0 / 3.0

    @pytest.mark.asyncio
    async def test_get_report_comprehensive(self):
        """Test comprehensive report generation"""
        metrics = ReliabilityMetrics()

        # Record steps
        await metrics.record_step("planner", success=True)
        await metrics.record_step("coder", success=True, required_compensation=True)
        await metrics.record_step("planner", success=False)

        # Record workflows
        await metrics.record_workflow("wf-1", steps=3, retries=1, success=True)

        report = await metrics.get_report()

        assert report.total_steps == 3
        assert report.total_workflows == 1
        assert 0.0 <= report.svr <= 1.0
        assert 0.0 <= report.cr <= 1.0
        assert report.pc >= 0.0

    @pytest.mark.asyncio
    async def test_get_report_with_agent_metrics(self):
        """Test report includes per-agent metrics"""
        metrics = ReliabilityMetrics()

        await metrics.record_step("planner", success=True)
        await metrics.record_step("planner", success=True)
        await metrics.record_step("coder", success=False)

        report = await metrics.get_report()

        assert "planner" in report.agent_metrics
        assert "coder" in report.agent_metrics
        assert report.agent_metrics["planner"].total_steps == 2
        assert report.agent_metrics["coder"].total_steps == 1

    @pytest.mark.asyncio
    async def test_get_report_with_finops_metrics(self):
        """Test report includes FinOps metrics"""
        metrics = ReliabilityMetrics()

        # Record steps with tool timing
        await metrics.storage.record_step({
            "agent": "planner",
            "success": True,
            "tool_duration_ms": 100
        })
        await metrics.storage.record_step({
            "agent": "coder",
            "success": True,
            "tool_duration_ms": 200
        })

        # Record workflows with duration
        await metrics.storage.record_workflow({
            "workflow_id": "wf-1",
            "steps": 2,
            "retries": 0,
            "success": True,
            "duration_ms": 5000
        })

        report = await metrics.get_report()

        assert report.tcl == 150.0
        assert report.wct == 5000.0
