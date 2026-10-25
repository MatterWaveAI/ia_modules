"""
Unit tests for decision trail system.

Tests Evidence, StepRecord, DecisionTrail, and DecisionTrailBuilder.
"""

import pytest
from ia_modules.reliability.decision_trail import (
    Evidence,
    StepRecord,
    ToolCall,
    DecisionTrail,
    DecisionTrailBuilder
)
from ia_modules.agents.state import StateManager
from ia_modules.tools.core import ToolRegistry


class MockCheckpointer:
    """Mock checkpointer for testing."""

    def __init__(self):
        self.checkpoints = {}

    async def get_checkpoint(self, thread_id, checkpoint_id):
        return self.checkpoints.get((thread_id, checkpoint_id))

    async def load_checkpoint(self, thread_id):
        # Return latest checkpoint for thread
        checkpoints = [tid for tid, _ in self.checkpoints.keys() if tid == thread_id]
        if checkpoints:
            return self.checkpoints[list(self.checkpoints.keys())[0]]
        return None


class MockCheckpoint:
    """Mock checkpoint object."""

    def __init__(self, checkpoint_id, metadata=None):
        self.checkpoint_id = checkpoint_id
        self.metadata = metadata or {}


class TestEvidence:
    """Test Evidence dataclass."""

    def test_evidence_creation_verified(self):
        """Evidence can be created with verified confidence."""
        evidence = Evidence(
            type="tool_result",
            source="search_api",
            content={"results": ["result1", "result2"]},
            timestamp="2025-01-01T00:00:00Z",
            confidence="verified"
        )

        assert evidence.type == "tool_result"
        assert evidence.source == "search_api"
        assert evidence.confidence == "verified"
        assert len(evidence.content["results"]) == 2

    def test_evidence_creation_claimed(self):
        """Evidence can be created with claimed confidence."""
        evidence = Evidence(
            type="agent_claim",
            source="planner_agent",
            content={"plan": ["step1", "step2"]},
            timestamp="2025-01-01T00:00:00Z",
            confidence="claimed"
        )

        assert evidence.type == "agent_claim"
        assert evidence.source == "planner_agent"
        assert evidence.confidence == "claimed"

    def test_evidence_with_metadata(self):
        """Evidence can include metadata."""
        evidence = Evidence(
            type="database_read",
            source="postgres",
            content={"user_id": 123},
            timestamp="2025-01-01T00:00:00Z",
            confidence="verified",
            metadata={"query": "SELECT * FROM users", "duration_ms": 50}
        )

        assert "query" in evidence.metadata
        assert evidence.metadata["duration_ms"] == 50


class TestStepRecord:
    """Test StepRecord dataclass."""

    def test_step_record_creation(self):
        """StepRecord can be created."""
        step = StepRecord(
            agent="planner",
            step_index=0,
            timestamp="2025-01-01T00:00:00Z",
            input_data={"task": "Create plan"},
            output_data={"plan": ["step1", "step2"]},
            success=True
        )

        assert step.agent == "planner"
        assert step.step_index == 0
        assert step.success is True
        assert step.retries == 0

    def test_step_record_with_error(self):
        """StepRecord can record failures."""
        step = StepRecord(
            agent="coder",
            step_index=1,
            timestamp="2025-01-01T00:00:00Z",
            input_data={},
            output_data={},
            success=False,
            error="Syntax error in generated code",
            retries=2
        )

        assert step.success is False
        assert step.error == "Syntax error in generated code"
        assert step.retries == 2

    def test_step_record_with_state_snapshots(self):
        """StepRecord can capture state before/after."""
        step = StepRecord(
            agent="writer",
            step_index=2,
            timestamp="2025-01-01T00:00:00Z",
            input_data={},
            output_data={},
            success=True,
            state_before={"draft": "version1"},
            state_after={"draft": "version2", "approved": False}
        )

        assert "draft" in step.state_before
        assert "approved" in step.state_after
        assert step.state_before["draft"] != step.state_after["draft"]


class TestDecisionTrail:
    """Test DecisionTrail dataclass."""

    def test_decision_trail_creation_minimal(self):
        """DecisionTrail can be created with minimal data."""
        trail = DecisionTrail(
            thread_id="thread-123",
            checkpoint_id="ckpt-456"
        )

        assert trail.thread_id == "thread-123"
        assert trail.checkpoint_id == "ckpt-456"
        assert trail.success is False
        assert len(trail.steps_taken) == 0

    def test_decision_trail_with_goal(self):
        """DecisionTrail can include goal and input."""
        trail = DecisionTrail(
            thread_id="thread-123",
            checkpoint_id="ckpt-456",
            goal="Generate article about AI",
            input_data={"topic": "AI agents", "length": 1000}
        )

        assert trail.goal == "Generate article about AI"
        assert trail.input_data["topic"] == "AI agents"

    def test_decision_trail_with_execution_path(self):
        """DecisionTrail can track execution path."""
        trail = DecisionTrail(
            thread_id="thread-123",
            checkpoint_id="ckpt-456",
            execution_path=["planner", "writer", "critic", "writer", "formatter"]
        )

        assert len(trail.execution_path) == 5
        assert trail.execution_path[0] == "planner"
        assert trail.execution_path[-1] == "formatter"

    def test_decision_trail_with_evidence(self):
        """DecisionTrail can collect evidence."""
        trail = DecisionTrail(
            thread_id="thread-123",
            checkpoint_id="ckpt-456"
        )

        trail.evidence.append(Evidence(
            type="tool_result",
            source="search",
            content={"results": []},
            timestamp="2025-01-01T00:00:00Z",
            confidence="verified"
        ))

        trail.evidence.append(Evidence(
            type="agent_claim",
            source="planner",
            content={"plan": []},
            timestamp="2025-01-01T00:00:00Z",
            confidence="claimed"
        ))

        assert len(trail.evidence) == 2
        verified = [e for e in trail.evidence if e.confidence == "verified"]
        claimed = [e for e in trail.evidence if e.confidence == "claimed"]
        assert len(verified) == 1
        assert len(claimed) == 1


@pytest.mark.asyncio
class TestDecisionTrailBuilder:
    """Test DecisionTrailBuilder."""

    @pytest.mark.asyncio
    async def test_builder_creation(self):
        """Builder can be created."""
        builder = DecisionTrailBuilder()

        assert builder.state_manager is None
        assert builder.tool_registry is None
        assert builder.checkpointer is None

    @pytest.mark.asyncio
    async def test_builder_with_components(self):
        """Builder can be created with components."""
        state = StateManager(thread_id="test")
        registry = ToolRegistry()
        checkpointer = MockCheckpointer()

        builder = DecisionTrailBuilder(
            state_manager=state,
            tool_registry=registry,
            checkpointer=checkpointer
        )

        assert builder.state_manager is not None
        assert builder.tool_registry is not None
        assert builder.checkpointer is not None

    @pytest.mark.asyncio
    async def test_build_trail_minimal(self):
        """Can build trail with minimal data."""
        builder = DecisionTrailBuilder()

        trail = await builder.build_trail("thread-123")

        assert trail.thread_id == "thread-123"
        assert trail.checkpoint_id == "unknown"
        assert isinstance(trail.duration_ms, int)

    @pytest.mark.asyncio
    async def test_build_trail_with_state_history(self):
        """Can build trail with state history."""
        state = StateManager(thread_id="test")
        builder = DecisionTrailBuilder(state_manager=state)

        # Simulate state changes
        await state.set("key1", "value1")
        await state.set("key2", "value2")
        await state.set("key1", "value1_updated")

        trail = await builder.build_trail("test")

        # Should have state deltas
        assert len(trail.state_deltas) > 0
        # Should have final state as outcome
        assert "key1" in trail.outcome
        assert trail.outcome["key1"] == "value1_updated"

    @pytest.mark.asyncio
    async def test_build_trail_with_tool_logs(self):
        """Can build trail with tool execution logs."""
        registry = ToolRegistry()
        builder = DecisionTrailBuilder(tool_registry=registry)

        # Execute tools to create logs
        await registry.execute("echo", {"message": "test1"})
        await registry.execute("calculator", {"expression": "2+2"})

        trail = await builder.build_trail("test")

        # Should have tool calls
        assert len(trail.tool_calls) == 2
        assert trail.tool_calls[0].tool_name == "echo"
        assert trail.tool_calls[1].tool_name == "calculator"

        # Should have evidence from tool calls
        assert len(trail.evidence) == 2
        assert all(e.confidence == "verified" for e in trail.evidence)

    @pytest.mark.asyncio
    async def test_build_trail_with_checkpoint(self):
        """Can build trail with checkpoint metadata."""
        checkpointer = MockCheckpointer()
        checkpointer.checkpoints[("thread-123", "ckpt-456")] = MockCheckpoint(
            checkpoint_id="ckpt-456",
            metadata={
                "goal": "Test goal",
                "input_data": {"test": "data"},
                "execution_path": ["agent1", "agent2"]
            }
        )

        builder = DecisionTrailBuilder(checkpointer=checkpointer)

        trail = await builder.build_trail("thread-123", "ckpt-456")

        assert trail.checkpoint_id == "ckpt-456"
        assert trail.goal == "Test goal"
        assert trail.input_data["test"] == "data"
        assert trail.execution_path == ["agent1", "agent2"]

    @pytest.mark.asyncio
    async def test_build_trail_success_determination(self):
        """Trail success is determined by tool call success."""
        registry = ToolRegistry()
        builder = DecisionTrailBuilder(tool_registry=registry)

        # All tools succeed
        await registry.execute("echo", {"message": "test"})

        trail = await builder.build_trail("test")
        assert trail.success is True

        # Tool fails
        try:
            await registry.execute("calculator", {"expression": "invalid"})
        except Exception:
            pass

        trail2 = await builder.build_trail("test")
        # Success should be False because one tool failed
        assert trail2.success is False

    @pytest.mark.asyncio
    async def test_explain_decision_minimal(self):
        """Can explain decision with minimal trail."""
        builder = DecisionTrailBuilder()

        trail = DecisionTrail(
            thread_id="thread-123",
            checkpoint_id="ckpt-456",
            goal="Test goal"
        )

        explanation = await builder.explain_decision(trail)

        assert "Decision Trail" in explanation
        assert "thread-123" in explanation
        assert "Test goal" in explanation

    @pytest.mark.asyncio
    async def test_explain_decision_with_execution_path(self):
        """Explanation includes execution path."""
        builder = DecisionTrailBuilder()

        trail = DecisionTrail(
            thread_id="thread-123",
            checkpoint_id="ckpt-456",
            execution_path=["planner", "coder", "critic"]
        )

        explanation = await builder.explain_decision(trail)

        assert "Execution Path" in explanation
        assert "planner" in explanation
        assert "coder" in explanation
        assert "critic" in explanation

    @pytest.mark.asyncio
    async def test_explain_decision_with_tool_calls(self):
        """Explanation includes tool calls."""
        builder = DecisionTrailBuilder()

        trail = DecisionTrail(
            thread_id="thread-123",
            checkpoint_id="ckpt-456"
        )

        trail.tool_calls.append(ToolCall(
            tool_name="search",
            parameters={"query": "test"},
            result={"results": ["r1", "r2"]},
            success=True,
            timestamp="2025-01-01T00:00:00Z",
            duration_ms=100
        ))

        explanation = await builder.explain_decision(trail)

        assert "Tool Calls" in explanation
        assert "search" in explanation
        assert "100ms" in explanation

    @pytest.mark.asyncio
    async def test_explain_decision_with_evidence(self):
        """Explanation includes evidence."""
        builder = DecisionTrailBuilder()

        trail = DecisionTrail(
            thread_id="thread-123",
            checkpoint_id="ckpt-456"
        )

        trail.evidence.append(Evidence(
            type="tool_result",
            source="api",
            content={"data": "verified"},
            timestamp="2025-01-01T00:00:00Z",
            confidence="verified"
        ))

        trail.evidence.append(Evidence(
            type="agent_claim",
            source="planner",
            content={"claim": "value"},
            timestamp="2025-01-01T00:00:00Z",
            confidence="claimed"
        ))

        explanation = await builder.explain_decision(trail, include_evidence=True)

        assert "Evidence" in explanation
        assert "Verified Facts" in explanation
        assert "Agent Claims" in explanation
