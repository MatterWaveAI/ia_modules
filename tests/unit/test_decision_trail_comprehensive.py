"""
Comprehensive tests for reliability.decision_trail module
"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from ia_modules.reliability.decision_trail import (
    Evidence,
    StepRecord,
    ToolCall,
    StateDelta,
    DecisionTrail,
    DecisionTrailBuilder
)


class TestEvidence:
    """Test Evidence dataclass"""

    def test_create_verified_evidence(self):
        """Test creating verified evidence"""
        evidence = Evidence(
            type="tool_result",
            source="search_api",
            content={"results": ["data"]},
            timestamp="2024-01-01T12:00:00Z",
            confidence="verified"
        )

        assert evidence.type == "tool_result"
        assert evidence.source == "search_api"
        assert evidence.confidence == "verified"
        assert evidence.metadata == {}

    def test_create_claimed_evidence(self):
        """Test creating claimed evidence"""
        evidence = Evidence(
            type="agent_claim",
            source="planner_agent",
            content={"plan": ["step1"]},
            timestamp="2024-01-01T12:00:00Z",
            confidence="claimed"
        )

        assert evidence.confidence == "claimed"

    def test_evidence_with_metadata(self):
        """Test evidence with metadata"""
        metadata = {"version": "1.0", "model": "gpt-4"}
        evidence = Evidence(
            type="llm_output",
            source="openai",
            content="Generated text",
            timestamp="2024-01-01T12:00:00Z",
            confidence="claimed",
            metadata=metadata
        )

        assert evidence.metadata == metadata


class TestStepRecord:
    """Test StepRecord dataclass"""

    def test_create_successful_step(self):
        """Test creating successful step record"""
        step = StepRecord(
            agent="planner",
            step_index=1,
            timestamp="2024-01-01T12:00:00Z",
            input_data={"request": "plan task"},
            output_data={"plan": ["step1", "step2"]},
            success=True,
            duration_ms=500
        )

        assert step.agent == "planner"
        assert step.success is True
        assert step.error is None
        assert step.retries == 0

    def test_create_failed_step(self):
        """Test creating failed step record"""
        step = StepRecord(
            agent="executor",
            step_index=2,
            timestamp="2024-01-01T12:01:00Z",
            input_data={"task": "execute"},
            output_data={},
            success=False,
            error="Execution failed",
            retries=2
        )

        assert step.success is False
        assert step.error == "Execution failed"
        assert step.retries == 2

    def test_step_with_state_tracking(self):
        """Test step with state before/after"""
        step = StepRecord(
            agent="researcher",
            step_index=1,
            timestamp="2024-01-01T12:00:00Z",
            input_data={},
            output_data={},
            success=True,
            state_before={"count": 0},
            state_after={"count": 5}
        )

        assert step.state_before == {"count": 0}
        assert step.state_after == {"count": 5}


class TestToolCall:
    """Test ToolCall dataclass"""

    def test_successful_tool_call(self):
        """Test successful tool call"""
        tool_call = ToolCall(
            tool_name="web_search",
            parameters={"query": "test"},
            result={"results": ["item1", "item2"]},
            success=True,
            timestamp="2024-01-01T12:00:00Z",
            duration_ms=1200
        )

        assert tool_call.tool_name == "web_search"
        assert tool_call.success is True
        assert tool_call.error is None

    def test_failed_tool_call(self):
        """Test failed tool call"""
        tool_call = ToolCall(
            tool_name="database_query",
            parameters={"query": "SELECT * FROM users"},
            result=None,
            success=False,
            timestamp="2024-01-01T12:00:00Z",
            error="Connection timeout"
        )

        assert tool_call.success is False
        assert tool_call.error == "Connection timeout"


class TestStateDelta:
    """Test StateDelta dataclass"""

    def test_state_change(self):
        """Test state delta record"""
        delta = StateDelta(
            key="counter",
            old_value=5,
            new_value=10,
            changed_by="incrementer_agent",
            timestamp="2024-01-01T12:00:00Z",
            version=2
        )

        assert delta.key == "counter"
        assert delta.old_value == 5
        assert delta.new_value == 10
        assert delta.changed_by == "incrementer_agent"
        assert delta.version == 2


class TestDecisionTrail:
    """Test DecisionTrail dataclass"""

    def test_create_minimal_trail(self):
        """Test creating minimal decision trail"""
        trail = DecisionTrail(
            thread_id="thread-123",
            checkpoint_id="checkpoint-456"
        )

        assert trail.thread_id == "thread-123"
        assert trail.checkpoint_id == "checkpoint-456"
        assert trail.goal == ""
        assert trail.success is False
        assert len(trail.steps_taken) == 0

    def test_create_complete_trail(self):
        """Test creating complete decision trail"""
        trail = DecisionTrail(
            thread_id="thread-123",
            checkpoint_id="checkpoint-456",
            goal="Complete user task",
            input_data={"user_request": "test"},
            plan=["step1", "step2"],
            execution_path=["planner", "executor"],
            success=True,
            duration_ms=5000,
            tokens_used=1500,
            cost_usd=0.05
        )

        assert trail.goal == "Complete user task"
        assert trail.execution_path == ["planner", "executor"]
        assert trail.success is True
        assert trail.tokens_used == 1500
        assert trail.cost_usd == 0.05

    def test_trail_with_steps_and_tools(self):
        """Test trail with steps and tool calls"""
        step = StepRecord(
            agent="planner",
            step_index=1,
            timestamp="2024-01-01T12:00:00Z",
            input_data={},
            output_data={},
            success=True
        )

        tool_call = ToolCall(
            tool_name="search",
            parameters={},
            result={"found": True},
            success=True,
            timestamp="2024-01-01T12:00:00Z"
        )

        trail = DecisionTrail(
            thread_id="thread-123",
            checkpoint_id="checkpoint-456",
            steps_taken=[step],
            tool_calls=[tool_call]
        )

        assert len(trail.steps_taken) == 1
        assert len(trail.tool_calls) == 1


@pytest.mark.asyncio
class TestDecisionTrailBuilder:
    """Test DecisionTrailBuilder"""

    async def test_init(self):
        """Test builder initialization"""
        builder = DecisionTrailBuilder()

        assert builder.state_manager is None
        assert builder.tool_registry is None
        assert builder.checkpointer is None

    async def test_init_with_dependencies(self):
        """Test builder with dependencies"""
        state_mgr = MagicMock()
        tool_reg = MagicMock()
        checkpointer = MagicMock()

        builder = DecisionTrailBuilder(state_mgr, tool_reg, checkpointer)

        assert builder.state_manager is state_mgr
        assert builder.tool_registry is tool_reg
        assert builder.checkpointer is checkpointer

    async def test_build_trail_minimal(self):
        """Test building minimal trail"""
        builder = DecisionTrailBuilder()

        trail = await builder.build_trail("thread-123", "checkpoint-456")

        assert trail.thread_id == "thread-123"
        assert trail.checkpoint_id == "checkpoint-456"
        assert isinstance(trail.duration_ms, int)
        assert trail.success is True  # No tools = assumed success

    async def test_build_trail_with_checkpointer(self):
        """Test building trail with checkpoint data"""
        checkpoint = MagicMock()
        checkpoint.checkpoint_id = "cp-123"
        checkpoint.metadata = {
            "goal": "Test goal",
            "input_data": {"key": "value"},
            "execution_path": ["agent1", "agent2"]
        }

        checkpointer = AsyncMock()
        checkpointer.load_checkpoint = AsyncMock(return_value=checkpoint)

        builder = DecisionTrailBuilder(checkpointer=checkpointer)
        trail = await builder.build_trail("thread-123")

        assert trail.goal == "Test goal"
        assert trail.input_data == {"key": "value"}
        assert trail.execution_path == ["agent1", "agent2"]

    async def test_build_trail_with_tool_registry(self):
        """Test building trail with tool execution logs"""
        tool_registry = MagicMock()
        tool_registry._execution_log = [
            {
                "tool": "search_api",
                "parameters": {"query": "test"},
                "result": {"found": True},
                "success": True,
                "timestamp": "2024-01-01T12:00:00Z",
                "duration": 1.5
            },
            {
                "tool": "database_query",
                "parameters": {"sql": "SELECT *"},
                "result": None,
                "success": False,
                "timestamp": "2024-01-01T12:01:00Z",
                "duration": 0.5,
                "error": "Connection failed"
            }
        ]

        builder = DecisionTrailBuilder(tool_registry=tool_registry)
        trail = await builder.build_trail("thread-123", "cp-123")

        assert len(trail.tool_calls) == 2
        assert trail.tool_calls[0].tool_name == "search_api"
        assert trail.tool_calls[0].success is True
        assert trail.tool_calls[0].duration_ms == 1500

        assert trail.tool_calls[1].success is False
        assert trail.tool_calls[1].error == "Connection failed"

        # Should have evidence from successful tool call
        assert len(trail.evidence) == 1
        assert trail.evidence[0].confidence == "verified"

    async def test_build_trail_without_evidence(self):
        """Test building trail without extracting evidence"""
        tool_registry = MagicMock()
        tool_registry._execution_log = [
            {
                "tool": "test_tool",
                "result": {"data": "test"},
                "success": True,
                "timestamp": "2024-01-01T12:00:00Z"
            }
        ]

        builder = DecisionTrailBuilder(tool_registry=tool_registry)
        trail = await builder.build_trail("thread-123", "cp-123", include_evidence=False)

        assert len(trail.tool_calls) == 1
        assert len(trail.evidence) == 0

    async def test_build_trail_success_determination(self):
        """Test trail success based on tool calls"""
        tool_registry = MagicMock()
        tool_registry._execution_log = [
            {"tool": "t1", "success": True, "timestamp": "2024-01-01T12:00:00Z"},
            {"tool": "t2", "success": True, "timestamp": "2024-01-01T12:00:00Z"},
        ]

        builder = DecisionTrailBuilder(tool_registry=tool_registry)
        trail = await builder.build_trail("thread-123", "cp-123")

        assert trail.success is True

        # Now test with failure
        tool_registry._execution_log.append(
            {"tool": "t3", "success": False, "timestamp": "2024-01-01T12:00:00Z"}
        )

        trail2 = await builder.build_trail("thread-456", "cp-456")
        assert trail2.success is False

    async def test_explain_decision_minimal(self):
        """Test explaining minimal decision trail"""
        trail = DecisionTrail(
            thread_id="thread-123",
            checkpoint_id="cp-456",
            timestamp="2024-01-01T12:00:00Z",
            success=True,
            duration_ms=1000
        )

        builder = DecisionTrailBuilder()
        explanation = await builder.explain_decision(trail)

        assert "# Decision Trail: thread-123" in explanation
        assert "**Success**: True" in explanation
        assert "Duration: 1000ms" in explanation

    async def test_explain_decision_with_goal(self):
        """Test explanation with goal"""
        trail = DecisionTrail(
            thread_id="thread-123",
            checkpoint_id="cp-456",
            goal="Complete user task"
        )

        builder = DecisionTrailBuilder()
        explanation = await builder.explain_decision(trail)

        assert "## Goal" in explanation
        assert "Complete user task" in explanation

    async def test_explain_decision_with_execution_path(self):
        """Test explanation with execution path"""
        trail = DecisionTrail(
            thread_id="thread-123",
            checkpoint_id="cp-456",
            execution_path=["planner", "executor", "formatter"]
        )

        builder = DecisionTrailBuilder()
        explanation = await builder.explain_decision(trail)

        assert "## Execution Path" in explanation
        assert "1. planner" in explanation
        assert "2. executor" in explanation
        assert "3. formatter" in explanation

    async def test_explain_decision_with_tool_calls(self):
        """Test explanation with tool calls"""
        tool_calls = [
            ToolCall(
                tool_name="search",
                parameters={"q": "test"},
                result={"found": True},
                success=True,
                timestamp="2024-01-01T12:00:00Z",
                duration_ms=500
            ),
            ToolCall(
                tool_name="database",
                parameters={},
                result=None,
                success=False,
                timestamp="2024-01-01T12:01:00Z",
                error="Failed"
            )
        ]

        trail = DecisionTrail(
            thread_id="thread-123",
            checkpoint_id="cp-456",
            tool_calls=tool_calls
        )

        builder = DecisionTrailBuilder()
        explanation = await builder.explain_decision(trail)

        assert "## Tool Calls (2 total)" in explanation
        assert "✓ **search**" in explanation
        assert "✗ **database**" in explanation
        assert "Duration: 500ms" in explanation
        assert "Error: Failed" in explanation

    async def test_explain_decision_with_evidence(self):
        """Test explanation with evidence"""
        evidence = [
            Evidence("tool_result", "api", {"data": "test"}, "2024-01-01T12:00:00Z", "verified"),
            Evidence("agent_claim", "planner", {"plan": []}, "2024-01-01T12:00:00Z", "claimed")
        ]

        trail = DecisionTrail(
            thread_id="thread-123",
            checkpoint_id="cp-456",
            evidence=evidence
        )

        builder = DecisionTrailBuilder()
        explanation = await builder.explain_decision(trail, include_evidence=True)

        assert "## Evidence (2 items)" in explanation
        assert "### Verified Facts (1)" in explanation
        assert "### Agent Claims (1)" in explanation

    async def test_explain_decision_without_evidence(self):
        """Test explanation without evidence section"""
        trail = DecisionTrail(
            thread_id="thread-123",
            checkpoint_id="cp-456",
            evidence=[Evidence("test", "src", {}, "2024-01-01T12:00:00Z", "verified")]
        )

        builder = DecisionTrailBuilder()
        explanation = await builder.explain_decision(trail, include_evidence=False)

        assert "## Evidence" not in explanation

    async def test_explain_decision_with_state_deltas(self):
        """Test explanation with state deltas"""
        deltas = [
            StateDelta("counter", 0, 5, "incrementer", "2024-01-01T12:00:00Z", 1),
            StateDelta("status", "pending", "complete", "executor", "2024-01-01T12:01:00Z", 2)
        ]

        trail = DecisionTrail(
            thread_id="thread-123",
            checkpoint_id="cp-456",
            state_deltas=deltas
        )

        builder = DecisionTrailBuilder()
        explanation = await builder.explain_decision(trail, include_state_deltas=True)

        assert "## State Changes (2)" in explanation
        assert "**counter**: 0 → 5" in explanation
        assert "**status**: pending → complete" in explanation

    async def test_explain_decision_with_metrics(self):
        """Test explanation with all metrics"""
        trail = DecisionTrail(
            thread_id="thread-123",
            checkpoint_id="cp-456",
            duration_ms=5000,
            tokens_used=1500,
            cost_usd=0.075
        )

        builder = DecisionTrailBuilder()
        explanation = await builder.explain_decision(trail)

        assert "## Metrics" in explanation
        assert "Duration: 5000ms" in explanation
        assert "Tokens: 1500" in explanation
        assert "Cost: $0.0750" in explanation
