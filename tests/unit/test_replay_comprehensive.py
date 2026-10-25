"""Comprehensive tests for reliability.replay module"""

import pytest
from unittest.mock import AsyncMock, MagicMock
from ia_modules.reliability.replay import (
    ReplayMode,
    Difference,
    ReplayResult,
    Replayer
)
from ia_modules.reliability.decision_trail import DecisionTrail, ToolCall


class TestReplayMode:
    """Test ReplayMode enum"""

    def test_strict_mode(self):
        """Test STRICT mode"""
        assert ReplayMode.STRICT.value == "strict"

    def test_simulated_mode(self):
        """Test SIMULATED mode"""
        assert ReplayMode.SIMULATED.value == "simulated"

    def test_counterfactual_mode(self):
        """Test COUNTERFACTUAL mode"""
        assert ReplayMode.COUNTERFACTUAL.value == "counterfactual"


class TestDifference:
    """Test Difference dataclass"""

    def test_init(self):
        """Test difference creation"""
        diff = Difference(
            field="result",
            original_value={"status": "ok"},
            replayed_value={"status": "error"},
            location="step_2",
            significance="critical"
        )

        assert diff.field == "result"
        assert diff.original_value == {"status": "ok"}
        assert diff.replayed_value == {"status": "error"}
        assert diff.location == "step_2"
        assert diff.significance == "critical"


class TestReplayResult:
    """Test ReplayResult dataclass"""

    def test_init(self):
        """Test result initialization"""
        result = ReplayResult(
            mode=ReplayMode.STRICT,
            success=True,
            original_outcome={"status": "ok"},
            replayed_outcome={"status": "ok"}
        )

        assert result.mode == ReplayMode.STRICT
        assert result.success is True
        assert len(result.differences) == 0

    def test_is_exact_match_true(self):
        """Test exact match detection"""
        result = ReplayResult(
            mode=ReplayMode.STRICT,
            success=True,
            original_outcome={},
            replayed_outcome={},
            differences=[]
        )

        assert result.is_exact_match is True

    def test_is_exact_match_false_differences(self):
        """Test no exact match with differences"""
        diff = Difference("field", "a", "b", "loc", "critical")
        result = ReplayResult(
            mode=ReplayMode.STRICT,
            success=True,
            original_outcome={},
            replayed_outcome={},
            differences=[diff]
        )

        assert result.is_exact_match is False

    def test_is_exact_match_false_failure(self):
        """Test no exact match on failure"""
        result = ReplayResult(
            mode=ReplayMode.STRICT,
            success=False,
            original_outcome={},
            replayed_outcome={},
            differences=[]
        )

        assert result.is_exact_match is False

    def test_critical_differences(self):
        """Test filtering critical differences"""
        diffs = [
            Difference("field1", "a", "b", "loc1", "critical"),
            Difference("field2", "c", "d", "loc2", "minor"),
            Difference("field3", "e", "f", "loc3", "critical"),
        ]

        result = ReplayResult(
            mode=ReplayMode.STRICT,
            success=True,
            original_outcome={},
            replayed_outcome={},
            differences=diffs
        )

        critical = result.critical_differences
        assert len(critical) == 2
        assert all(d.significance == "critical" for d in critical)

    def test_metadata(self):
        """Test metadata storage"""
        result = ReplayResult(
            mode=ReplayMode.SIMULATED,
            success=True,
            original_outcome={},
            replayed_outcome={},
            metadata={"mocked_tools": ["search", "fetch"]}
        )

        assert "mocked_tools" in result.metadata


class TestReplayer:
    """Test Replayer class"""

    def setup_method(self):
        """Set up test fixtures"""
        self.trail = DecisionTrail(
            thread_id="thread-123",
            checkpoint_id="cp-123"
        )
        self.trail.execution_path = ["planner"]
        self.trail.input_data = {"query": "test"}
        self.trail.outcome = {"result": "success"}

    def test_init(self):
        """Test replayer initialization"""
        replayer = Replayer(self.trail)
        assert replayer.trail == self.trail
        assert len(replayer.mock_tools) == 0

    def test_set_mock_tool(self):
        """Test setting mock tool"""
        replayer = Replayer(self.trail)

        def mock_search():
            return {"results": []}

        replayer.set_mock_tool("search", mock_search)
        assert "search" in replayer.mock_tools

    @pytest.mark.asyncio
    async def test_strict_replay_no_orchestrator(self):
        """Test strict replay without orchestrator"""
        replayer = Replayer(self.trail)

        result = await replayer.strict_replay()

        assert result.success is False
        assert "Orchestrator required" in result.error

    @pytest.mark.asyncio
    async def test_strict_replay_success(self):
        """Test successful strict replay"""
        replayer = Replayer(self.trail)

        # Mock orchestrator
        orchestrator = AsyncMock()
        orchestrator.run = AsyncMock(return_value={"result": "success"})

        result = await replayer.strict_replay(orchestrator=orchestrator)

        assert result.success is True
        assert result.mode == ReplayMode.STRICT
        assert result.is_exact_match is True

    @pytest.mark.asyncio
    async def test_strict_replay_with_differences(self):
        """Test strict replay with differences"""
        replayer = Replayer(self.trail)

        # Mock orchestrator with different outcome
        orchestrator = AsyncMock()
        orchestrator.run = AsyncMock(return_value={"result": "different"})

        result = await replayer.strict_replay(orchestrator=orchestrator)

        assert result.success is True
        assert result.is_exact_match is False
        assert len(result.differences) > 0

    @pytest.mark.asyncio
    async def test_strict_replay_exception(self):
        """Test strict replay with exception"""
        replayer = Replayer(self.trail)

        orchestrator = AsyncMock()
        orchestrator.run = AsyncMock(side_effect=Exception("Replay failed"))

        result = await replayer.strict_replay(orchestrator=orchestrator)

        assert result.success is False
        assert "Replay failed" in result.error

    @pytest.mark.asyncio
    async def test_strict_replay_with_tool_registry(self):
        """Test strict replay with tool registry"""
        # Add tool calls to trail
        self.trail.tool_calls = [
            ToolCall(
                tool_name="search",
                parameters={"query": "test"},
                result={"results": []},
                success=True,
                timestamp="2024-01-01T00:00:00Z"
            )
        ]

        replayer = Replayer(self.trail)

        orchestrator = AsyncMock()
        orchestrator.run = AsyncMock(return_value={"result": "success"})

        tool_registry = MagicMock()
        tool_registry._execution_log = [
            {"tool": "search", "success": True}
        ]

        result = await replayer.strict_replay(
            orchestrator=orchestrator,
            tool_registry=tool_registry
        )

        assert result.success is True

    @pytest.mark.asyncio
    async def test_simulated_replay(self):
        """Test simulated replay"""
        # Add tool calls to trail
        self.trail.tool_calls = [
            ToolCall(
                tool_name="search",
                parameters={},
                result={"results": ["a", "b"]},
                success=True,
                timestamp="2024-01-01"
            )
        ]

        replayer = Replayer(self.trail)

        result = await replayer.simulated_replay()

        assert result.success is True
        assert result.mode == ReplayMode.SIMULATED
        assert "mocked_tools" in result.metadata

    @pytest.mark.asyncio
    async def test_simulated_replay_exception(self):
        """Test simulated replay with exception"""
        # Create trail that will cause error
        trail = DecisionTrail(
            thread_id="thread-123",
            checkpoint_id="cp-123"
        )

        replayer = Replayer(trail)

        # Force an exception by breaking the trail
        original_tool_calls = replayer.trail.tool_calls
        replayer.trail.tool_calls = None

        result = await replayer.simulated_replay()

        # Restore
        replayer.trail.tool_calls = original_tool_calls

        assert result.success is False

    @pytest.mark.asyncio
    async def test_counterfactual_replay_no_orchestrator(self):
        """Test counterfactual replay without orchestrator"""
        replayer = Replayer(self.trail)

        result = await replayer.counterfactual_replay({"query": "alternative"})

        assert result.success is False
        assert "Orchestrator required" in result.error

    @pytest.mark.asyncio
    async def test_counterfactual_replay_success(self):
        """Test successful counterfactual replay"""
        replayer = Replayer(self.trail)

        orchestrator = AsyncMock()
        orchestrator.run = AsyncMock(return_value={"result": "alternative_outcome"})

        result = await replayer.counterfactual_replay(
            {"query": "alternative"},
            orchestrator=orchestrator
        )

        assert result.success is True
        assert result.mode == ReplayMode.COUNTERFACTUAL
        assert result.metadata["original_inputs"] == {"query": "test"}
        assert result.metadata["alternative_inputs"] == {"query": "alternative"}

    @pytest.mark.asyncio
    async def test_counterfactual_replay_differences_marked_expected(self):
        """Test counterfactual differences marked as expected"""
        replayer = Replayer(self.trail)

        orchestrator = AsyncMock()
        orchestrator.run = AsyncMock(return_value={"result": "different"})

        result = await replayer.counterfactual_replay(
            {"query": "alternative"},
            orchestrator=orchestrator
        )

        # All differences should be marked as "expected"
        for diff in result.differences:
            assert diff.significance == "expected"

    @pytest.mark.asyncio
    async def test_counterfactual_replay_exception(self):
        """Test counterfactual replay with exception"""
        replayer = Replayer(self.trail)

        orchestrator = AsyncMock()
        orchestrator.run = AsyncMock(side_effect=Exception("Counterfactual failed"))

        result = await replayer.counterfactual_replay(
            {"query": "alternative"},
            orchestrator=orchestrator
        )

        assert result.success is False
        assert "Counterfactual failed" in result.error

    def test_compare_outcomes_identical(self):
        """Test comparing identical outcomes"""
        replayer = Replayer(self.trail)

        original = {"status": "ok", "count": 5}
        replayed = {"status": "ok", "count": 5}

        differences = replayer._compare_outcomes(original, replayed)
        assert len(differences) == 0

    def test_compare_outcomes_different_values(self):
        """Test comparing different outcomes"""
        replayer = Replayer(self.trail)

        original = {"status": "ok", "count": 5}
        replayed = {"status": "error", "count": 5}

        differences = replayer._compare_outcomes(original, replayed)
        assert len(differences) == 1
        assert differences[0].field == "status"

    def test_compare_outcomes_missing_keys(self):
        """Test comparing outcomes with missing keys"""
        replayer = Replayer(self.trail)

        original = {"status": "ok", "count": 5}
        replayed = {"status": "ok"}

        differences = replayer._compare_outcomes(original, replayed)
        assert len(differences) == 1
        assert differences[0].field == "count"

    def test_compare_outcomes_extra_keys(self):
        """Test comparing outcomes with extra keys"""
        replayer = Replayer(self.trail)

        original = {"status": "ok"}
        replayed = {"status": "ok", "extra": "data"}

        differences = replayer._compare_outcomes(original, replayed)
        assert len(differences) == 1
        assert differences[0].field == "extra"

    def test_compare_outcomes_private_fields_minor(self):
        """Test private fields marked as minor"""
        replayer = Replayer(self.trail)

        original = {"_internal": "a"}
        replayed = {"_internal": "b"}

        differences = replayer._compare_outcomes(original, replayed)
        assert differences[0].significance == "minor"

    def test_compare_outcomes_public_fields_critical(self):
        """Test public fields marked as critical"""
        replayer = Replayer(self.trail)

        original = {"public": "a"}
        replayed = {"public": "b"}

        differences = replayer._compare_outcomes(original, replayed)
        assert differences[0].significance == "critical"

    def test_compare_tool_calls_identical(self):
        """Test comparing identical tool calls"""
        replayer = Replayer(self.trail)

        original_calls = [
            ToolCall("search", {}, {}, True, "2024"),
            ToolCall("fetch", {}, {}, True, "2024")
        ]

        replayed_log = [
            {"tool": "search"},
            {"tool": "fetch"}
        ]

        differences = replayer._compare_tool_calls(original_calls, replayed_log)
        assert len(differences) == 0

    def test_compare_tool_calls_different_count(self):
        """Test comparing tool calls with different counts"""
        replayer = Replayer(self.trail)

        original_calls = [
            ToolCall("search", {}, {}, True, "2024")
        ]

        replayed_log = [
            {"tool": "search"},
            {"tool": "fetch"}
        ]

        differences = replayer._compare_tool_calls(original_calls, replayed_log)
        assert len(differences) >= 1
        assert differences[0].field == "tool_call_count"

    def test_compare_tool_calls_different_tools(self):
        """Test comparing tool calls with different tools"""
        replayer = Replayer(self.trail)

        original_calls = [
            ToolCall("search", {}, {}, True, "2024")
        ]

        replayed_log = [
            {"tool": "fetch"}
        ]

        differences = replayer._compare_tool_calls(original_calls, replayed_log)
        assert any(d.field == "tool_name" for d in differences)

    @pytest.mark.asyncio
    async def test_replay_duration_measured(self):
        """Test that replay duration is measured"""
        replayer = Replayer(self.trail)

        orchestrator = AsyncMock()
        orchestrator.run = AsyncMock(return_value={"result": "success"})

        result = await replayer.strict_replay(orchestrator=orchestrator)

        assert result.duration_ms >= 0

    def test_multiple_mock_tools(self):
        """Test setting multiple mock tools"""
        replayer = Replayer(self.trail)

        replayer.set_mock_tool("search", lambda: {"results": []})
        replayer.set_mock_tool("fetch", lambda: {"data": {}})

        assert len(replayer.mock_tools) == 2
        assert "search" in replayer.mock_tools
        assert "fetch" in replayer.mock_tools
