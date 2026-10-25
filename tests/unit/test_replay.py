"""
Unit tests for replay system.

Tests ReplayMode, Difference, ReplayResult, and Replayer.
"""

from ia_modules.reliability.replay import (
    ReplayMode,
    Difference,
    ReplayResult,
    Replayer
)
from ia_modules.reliability.decision_trail import (
    DecisionTrail,
    ToolCall
)
from ia_modules.agents.state import StateManager
from ia_modules.agents.orchestrator import AgentOrchestrator
from ia_modules.agents.core import BaseAgent, AgentRole


class DummyAgent(BaseAgent):
    """Dummy agent for testing."""

    async def execute(self, input_data):
        # Write to state
        await self.write_state("executed", True)
        await self.write_state("input_received", input_data)
        return {"status": "success"}


class TestReplayMode:
    """Test ReplayMode enum."""

    def test_replay_modes_exist(self):
        """All replay modes are defined."""
        assert ReplayMode.STRICT
        assert ReplayMode.SIMULATED
        assert ReplayMode.COUNTERFACTUAL

    def test_replay_mode_values(self):
        """Replay modes have correct string values."""
        assert ReplayMode.STRICT.value == "strict"
        assert ReplayMode.SIMULATED.value == "simulated"
        assert ReplayMode.COUNTERFACTUAL.value == "counterfactual"


class TestDifference:
    """Test Difference dataclass."""

    def test_difference_creation(self):
        """Difference can be created."""
        diff = Difference(
            field="key1",
            original_value="value1",
            replayed_value="value2",
            location="step_1",
            significance="critical"
        )

        assert diff.field == "key1"
        assert diff.original_value == "value1"
        assert diff.replayed_value == "value2"
        assert diff.significance == "critical"

    def test_difference_significance_levels(self):
        """Difference can have different significance levels."""
        critical = Difference(
            field="result",
            original_value="A",
            replayed_value="B",
            location="outcome",
            significance="critical"
        )

        minor = Difference(
            field="_timestamp",
            original_value="2025-01-01",
            replayed_value="2025-01-02",
            location="metadata",
            significance="minor"
        )

        assert critical.significance == "critical"
        assert minor.significance == "minor"


class TestReplayResult:
    """Test ReplayResult dataclass."""

    def test_replay_result_creation(self):
        """ReplayResult can be created."""
        result = ReplayResult(
            mode=ReplayMode.STRICT,
            success=True,
            original_outcome={"key": "value1"},
            replayed_outcome={"key": "value1"}
        )

        assert result.mode == ReplayMode.STRICT
        assert result.success is True
        assert len(result.differences) == 0

    def test_is_exact_match_true(self):
        """is_exact_match returns True when no differences."""
        result = ReplayResult(
            mode=ReplayMode.STRICT,
            success=True,
            original_outcome={"key": "value"},
            replayed_outcome={"key": "value"},
            differences=[]
        )

        assert result.is_exact_match is True

    def test_is_exact_match_false(self):
        """is_exact_match returns False when differences exist."""
        result = ReplayResult(
            mode=ReplayMode.STRICT,
            success=True,
            original_outcome={"key": "value1"},
            replayed_outcome={"key": "value2"},
            differences=[
                Difference("key", "value1", "value2", "outcome", "critical")
            ]
        )

        assert result.is_exact_match is False

    def test_critical_differences_filter(self):
        """critical_differences returns only critical differences."""
        result = ReplayResult(
            mode=ReplayMode.STRICT,
            success=True,
            original_outcome={},
            replayed_outcome={},
            differences=[
                Difference("key1", "v1", "v2", "outcome", "critical"),
                Difference("key2", "v1", "v2", "outcome", "minor"),
                Difference("key3", "v1", "v2", "outcome", "critical"),
            ]
        )

        critical = result.critical_differences
        assert len(critical) == 2
        assert all(d.significance == "critical" for d in critical)


class TestReplayer:
    """Test Replayer class."""

    async def test_replayer_creation(self):
        """Replayer can be created with decision trail."""
        trail = DecisionTrail(
            thread_id="test-123",
            checkpoint_id="ckpt-456"
        )

        replayer = Replayer(trail)

        assert replayer.trail == trail
        assert len(replayer.mock_tools) == 0

    async def test_set_mock_tool(self):
        """Can set mock tool functions."""
        trail = DecisionTrail(thread_id="test", checkpoint_id="ckpt")
        replayer = Replayer(trail)

        async def mock_search(**kwargs):
            return {"results": ["mocked"]}

        replayer.set_mock_tool("search", mock_search)

        assert "search" in replayer.mock_tools
        assert replayer.mock_tools["search"] == mock_search

    async def test_strict_replay_no_orchestrator(self):
        """Strict replay fails without orchestrator."""
        trail = DecisionTrail(
            thread_id="test",
            checkpoint_id="ckpt",
            input_data={"test": "data"}
        )

        replayer = Replayer(trail)
        result = await replayer.strict_replay()

        assert result.mode == ReplayMode.STRICT
        assert result.success is False
        assert "Orchestrator required" in result.error

    async def test_strict_replay_with_orchestrator(self):
        """Strict replay executes with orchestrator."""
        # Create trail
        trail = DecisionTrail(
            thread_id="test",
            checkpoint_id="ckpt",
            input_data={"value": "test"},
            execution_path=["dummy"],
            outcome={"executed": True, "input_received": {"value": "test"}}
        )

        # Create orchestrator
        state = StateManager(thread_id="replay-test")
        orchestrator = AgentOrchestrator(state)

        role = AgentRole(name="dummy", description="Test agent")
        agent = DummyAgent(role, state)
        orchestrator.add_agent("dummy", agent)

        replayer = Replayer(trail)
        result = await replayer.strict_replay(orchestrator=orchestrator)

        assert result.mode == ReplayMode.STRICT
        assert result.success is True
        assert "executed" in result.replayed_outcome

    async def test_strict_replay_finds_differences(self):
        """Strict replay detects outcome differences."""
        # Trail with different outcome
        trail = DecisionTrail(
            thread_id="test",
            checkpoint_id="ckpt",
            input_data={"value": "original"},
            execution_path=["dummy"],
            outcome={"key": "original_value"}
        )

        # Orchestrator will produce different outcome
        state = StateManager(thread_id="replay-test")
        orchestrator = AgentOrchestrator(state)

        role = AgentRole(name="dummy", description="Test agent")
        agent = DummyAgent(role, state)
        orchestrator.add_agent("dummy", agent)

        replayer = Replayer(trail)
        result = await replayer.strict_replay(orchestrator=orchestrator)

        # Should find differences
        assert len(result.differences) > 0

    async def test_simulated_replay(self):
        """Simulated replay with mocked tools."""
        trail = DecisionTrail(
            thread_id="test",
            checkpoint_id="ckpt",
            input_data={"query": "test"},
            tool_calls=[
                ToolCall(
                    tool_name="search",
                    parameters={"query": "test"},
                    result={"results": ["result1", "result2"]},
                    success=True,
                    timestamp="2025-01-01T00:00:00Z"
                )
            ],
            outcome={"results_count": 2}
        )

        replayer = Replayer(trail)
        result = await replayer.simulated_replay()

        assert result.mode == ReplayMode.SIMULATED
        assert result.success is True
        # Should have mocked the search tool
        assert "mocked_tools" in result.metadata
        assert "search" in result.metadata["mocked_tools"]

    async def test_counterfactual_replay_no_orchestrator(self):
        """Counterfactual replay fails without orchestrator."""
        trail = DecisionTrail(thread_id="test", checkpoint_id="ckpt")
        replayer = Replayer(trail)

        result = await replayer.counterfactual_replay({"alternative": "input"})

        assert result.mode == ReplayMode.COUNTERFACTUAL
        assert result.success is False
        assert "Orchestrator required" in result.error

    async def test_counterfactual_replay_with_different_inputs(self):
        """Counterfactual replay runs with alternative inputs."""
        trail = DecisionTrail(
            thread_id="test",
            checkpoint_id="ckpt",
            input_data={"value": "original"},
            execution_path=["dummy"],
            outcome={"input_received": {"value": "original"}}
        )

        # Create orchestrator
        state = StateManager(thread_id="counterfactual-test")
        orchestrator = AgentOrchestrator(state)

        role = AgentRole(name="dummy", description="Test agent")
        agent = DummyAgent(role, state)
        orchestrator.add_agent("dummy", agent)

        replayer = Replayer(trail)
        alternative_inputs = {"value": "alternative"}

        result = await replayer.counterfactual_replay(
            alternative_inputs,
            orchestrator=orchestrator
        )

        assert result.mode == ReplayMode.COUNTERFACTUAL
        assert result.success is True
        assert result.metadata["original_inputs"] == {"value": "original"}
        assert result.metadata["alternative_inputs"] == alternative_inputs

    async def test_counterfactual_marks_differences_as_expected(self):
        """Counterfactual replay marks all differences as expected."""
        trail = DecisionTrail(
            thread_id="test",
            checkpoint_id="ckpt",
            input_data={"value": "A"},
            execution_path=["dummy"],
            outcome={"result": "A"}
        )

        state = StateManager(thread_id="counterfactual-test")
        orchestrator = AgentOrchestrator(state)

        role = AgentRole(name="dummy", description="Test agent")
        agent = DummyAgent(role, state)
        orchestrator.add_agent("dummy", agent)

        replayer = Replayer(trail)
        result = await replayer.counterfactual_replay(
            {"value": "B"},
            orchestrator=orchestrator
        )

        # All differences should be marked "expected"
        for diff in result.differences:
            assert diff.significance == "expected"

    async def test_compare_outcomes_no_differences(self):
        """_compare_outcomes finds no differences when outcomes match."""
        trail = DecisionTrail(thread_id="test", checkpoint_id="ckpt")
        replayer = Replayer(trail)

        original = {"key1": "value1", "key2": 123}
        replayed = {"key1": "value1", "key2": 123}

        differences = replayer._compare_outcomes(original, replayed)

        assert len(differences) == 0

    async def test_compare_outcomes_finds_differences(self):
        """_compare_outcomes finds differences in outcomes."""
        trail = DecisionTrail(thread_id="test", checkpoint_id="ckpt")
        replayer = Replayer(trail)

        original = {"key1": "value1", "key2": 123}
        replayed = {"key1": "value2", "key2": 123}

        differences = replayer._compare_outcomes(original, replayed)

        assert len(differences) == 1
        assert differences[0].field == "key1"
        assert differences[0].original_value == "value1"
        assert differences[0].replayed_value == "value2"

    async def test_compare_outcomes_missing_keys(self):
        """_compare_outcomes handles missing keys."""
        trail = DecisionTrail(thread_id="test", checkpoint_id="ckpt")
        replayer = Replayer(trail)

        original = {"key1": "value1", "key2": 123}
        replayed = {"key1": "value1", "key3": 456}

        differences = replayer._compare_outcomes(original, replayed)

        # Should find differences for key2 (missing in replayed) and key3 (missing in original)
        assert len(differences) == 2

        keys_with_diffs = {d.field for d in differences}
        assert "key2" in keys_with_diffs
        assert "key3" in keys_with_diffs
