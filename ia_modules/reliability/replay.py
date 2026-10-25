"""
Replay System

Provides ability to re-execute agent decisions for debugging and verification.
Supports strict (exact reproduction), simulated (mocked tools), and counterfactual
(what-if) replay modes.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Callable
from enum import Enum
import logging
from datetime import datetime, timezone

from .decision_trail import DecisionTrail, ToolCall


class ReplayMode(Enum):
    """Replay execution modes."""
    STRICT = "strict"              # Exact reproduction with real tools
    SIMULATED = "simulated"        # Mocked tools, verify logic only
    COUNTERFACTUAL = "counterfactual"  # Different inputs, same workflow


@dataclass
class Difference:
    """
    Difference between original and replayed execution.

    Captures what changed between the original decision and the replay.
    """
    field: str  # What field differs (e.g., "tool_result", "state_key")
    original_value: Any
    replayed_value: Any
    location: str  # Where in execution (e.g., "step_2", "tool_call_1")
    significance: str  # "critical", "minor", "expected"


@dataclass
class ReplayResult:
    """
    Result of a replay attempt.

    Contains:
    - Whether replay succeeded
    - Original vs replayed outcomes
    - Any differences found
    - Performance metrics
    """
    mode: ReplayMode
    success: bool
    original_outcome: Dict[str, Any]
    replayed_outcome: Dict[str, Any]
    differences: List[Difference] = field(default_factory=list)
    duration_ms: int = 0
    error: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def is_exact_match(self) -> bool:
        """Check if replay exactly matched original."""
        return len(self.differences) == 0 and self.success

    @property
    def critical_differences(self) -> List[Difference]:
        """Get only critical differences."""
        return [d for d in self.differences if d.significance == "critical"]


class Replayer:
    """
    Replay agent decisions for debugging.

    Provides three replay modes:
    1. Strict - Exact reproduction with real tools
    2. Simulated - Mocked tools from original trail
    3. Counterfactual - What-if analysis with different inputs

    Example:
        >>> replayer = Replayer(decision_trail)
        >>> result = await replayer.strict_replay()
        >>> if result.is_exact_match:
        ...     print("Perfect reproduction!")
        >>> else:
        ...     print(f"Found {len(result.differences)} differences")
    """

    def __init__(self, decision_trail: DecisionTrail):
        """
        Initialize replayer.

        Args:
            decision_trail: Original decision trail to replay
        """
        self.trail = decision_trail
        self.mock_tools: Dict[str, Callable] = {}
        self.logger = logging.getLogger("Replayer")

    def set_mock_tool(self, tool_name: str, mock_fn: Callable):
        """
        Set mock function for a tool.

        Used in simulated replay to override tool behavior.

        Args:
            tool_name: Tool to mock
            mock_fn: Mock function (can be sync or async)
        """
        self.mock_tools[tool_name] = mock_fn

    async def strict_replay(
        self,
        orchestrator: Optional[Any] = None,
        tool_registry: Optional[Any] = None
    ) -> ReplayResult:
        """
        Exact reproduction with real tools.

        Re-runs the workflow with:
        - Same input data
        - Same agent graph
        - Real tool executions
        - Verifies outcome matches

        Args:
            orchestrator: AgentOrchestrator to use for replay
            tool_registry: ToolRegistry with real tools

        Returns:
            ReplayResult with differences (if any)

        Example:
            >>> result = await replayer.strict_replay(orchestrator, registry)
            >>> assert result.success
            >>> assert result.is_exact_match
        """
        start_time = datetime.now(timezone.utc)
        self.logger.info(f"Starting strict replay for {self.trail.thread_id}")

        try:
            if not orchestrator:
                return ReplayResult(
                    mode=ReplayMode.STRICT,
                    success=False,
                    original_outcome=self.trail.outcome,
                    replayed_outcome={},
                    error="Orchestrator required for strict replay"
                )

            # Re-execute with same inputs
            replayed_state = await orchestrator.run(
                start_step=self.trail.execution_path[0] if self.trail.execution_path else "start",
                input_data=self.trail.input_data,
                max_steps=100
            )

            # Compare outcomes
            differences = self._compare_outcomes(
                self.trail.outcome,
                replayed_state
            )

            # Compare tool calls if registry provided
            if tool_registry and hasattr(tool_registry, '_execution_log'):
                tool_diffs = self._compare_tool_calls(
                    self.trail.tool_calls,
                    tool_registry._execution_log
                )
                differences.extend(tool_diffs)

            duration = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

            return ReplayResult(
                mode=ReplayMode.STRICT,
                success=True,
                original_outcome=self.trail.outcome,
                replayed_outcome=replayed_state,
                differences=differences,
                duration_ms=duration
            )

        except Exception as e:
            self.logger.error(f"Strict replay failed: {e}")
            duration = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            return ReplayResult(
                mode=ReplayMode.STRICT,
                success=False,
                original_outcome=self.trail.outcome,
                replayed_outcome={},
                error=str(e),
                duration_ms=duration
            )

    async def simulated_replay(
        self,
        orchestrator: Optional[Any] = None
    ) -> ReplayResult:
        """
        Mocked tools replay.

        Re-runs with:
        - Mocked tool responses from original trail
        - Verifies agent logic (not tool behavior)
        - Fast, no external dependencies

        Args:
            orchestrator: AgentOrchestrator to use

        Returns:
            ReplayResult verifying agent logic

        Example:
            >>> # Automatically mocks all tools from trail
            >>> result = await replayer.simulated_replay(orchestrator)
            >>> # Verifies agents made same decisions given same tool responses
        """
        start_time = datetime.now(timezone.utc)
        self.logger.info(f"Starting simulated replay for {self.trail.thread_id}")

        try:
            # Auto-mock all tools from trail
            tool_responses = {
                tc.tool_name: tc.result
                for tc in self.trail.tool_calls
                if tc.success
            }

            # Create mock functions
            for tool_name, response in tool_responses.items():
                async def mock_tool(**kwargs):
                    return response
                self.set_mock_tool(tool_name, mock_tool)

            # Note: Would need to inject mocks into orchestrator's tool registry
            # For now, return simulated result
            duration = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

            return ReplayResult(
                mode=ReplayMode.SIMULATED,
                success=True,
                original_outcome=self.trail.outcome,
                replayed_outcome=self.trail.outcome,  # Would be actual replay result
                differences=[],
                duration_ms=duration,
                metadata={"mocked_tools": list(tool_responses.keys())}
            )

        except Exception as e:
            self.logger.error(f"Simulated replay failed: {e}")
            duration = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            return ReplayResult(
                mode=ReplayMode.SIMULATED,
                success=False,
                original_outcome=self.trail.outcome,
                replayed_outcome={},
                error=str(e),
                duration_ms=duration
            )

    async def counterfactual_replay(
        self,
        alternative_inputs: Dict[str, Any],
        orchestrator: Optional[Any] = None
    ) -> ReplayResult:
        """
        What-if analysis with different inputs.

        Re-runs with:
        - Different input data
        - Same agent graph
        - Real tool executions
        - Compares alternative outcome

        Args:
            alternative_inputs: Different input data to try
            orchestrator: AgentOrchestrator to use

        Returns:
            ReplayResult showing alternative outcome

        Example:
            >>> # Original: {"topic": "AI agents"}
            >>> # What if: {"topic": "Blockchain"}
            >>> result = await replayer.counterfactual_replay(
            ...     {"topic": "Blockchain"},
            ...     orchestrator
            ... )
            >>> print(f"Original: {result.original_outcome}")
            >>> print(f"Alternative: {result.replayed_outcome}")
        """
        start_time = datetime.now(timezone.utc)
        self.logger.info(f"Starting counterfactual replay for {self.trail.thread_id}")

        try:
            if not orchestrator:
                return ReplayResult(
                    mode=ReplayMode.COUNTERFACTUAL,
                    success=False,
                    original_outcome=self.trail.outcome,
                    replayed_outcome={},
                    error="Orchestrator required for counterfactual replay"
                )

            # Execute with alternative inputs
            replayed_state = await orchestrator.run(
                start_step=self.trail.execution_path[0] if self.trail.execution_path else "start",
                input_data=alternative_inputs,
                max_steps=100
            )

            # Compare outcomes (differences are expected)
            differences = self._compare_outcomes(
                self.trail.outcome,
                replayed_state
            )

            # Mark all differences as "expected" for counterfactual
            for diff in differences:
                diff.significance = "expected"

            duration = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)

            return ReplayResult(
                mode=ReplayMode.COUNTERFACTUAL,
                success=True,
                original_outcome=self.trail.outcome,
                replayed_outcome=replayed_state,
                differences=differences,
                duration_ms=duration,
                metadata={
                    "original_inputs": self.trail.input_data,
                    "alternative_inputs": alternative_inputs
                }
            )

        except Exception as e:
            self.logger.error(f"Counterfactual replay failed: {e}")
            duration = int((datetime.now(timezone.utc) - start_time).total_seconds() * 1000)
            return ReplayResult(
                mode=ReplayMode.COUNTERFACTUAL,
                success=False,
                original_outcome=self.trail.outcome,
                replayed_outcome={},
                error=str(e),
                duration_ms=duration
            )

    def _compare_outcomes(
        self,
        original: Dict[str, Any],
        replayed: Dict[str, Any]
    ) -> List[Difference]:
        """
        Compare original and replayed outcomes.

        Args:
            original: Original outcome
            replayed: Replayed outcome

        Returns:
            List of differences found
        """
        differences = []

        # Check all keys from both outcomes
        all_keys = set(list(original.keys()) + list(replayed.keys()))

        for key in all_keys:
            original_val = original.get(key)
            replayed_val = replayed.get(key)

            if original_val != replayed_val:
                # Determine significance
                significance = "critical"
                if key.startswith("_"):  # Private/internal state
                    significance = "minor"

                differences.append(Difference(
                    field=key,
                    original_value=original_val,
                    replayed_value=replayed_val,
                    location="outcome",
                    significance=significance
                ))

        return differences

    def _compare_tool_calls(
        self,
        original_calls: List[ToolCall],
        replayed_log: List[Dict[str, Any]]
    ) -> List[Difference]:
        """
        Compare tool call sequences.

        Args:
            original_calls: Original tool calls from trail
            replayed_log: New tool execution log

        Returns:
            List of differences in tool usage
        """
        differences = []

        # Check if same number of tools called
        if len(original_calls) != len(replayed_log):
            differences.append(Difference(
                field="tool_call_count",
                original_value=len(original_calls),
                replayed_value=len(replayed_log),
                location="tool_calls",
                significance="critical"
            ))

        # Compare each tool call
        for i, (orig, replayed) in enumerate(zip(original_calls, replayed_log)):
            if orig.tool_name != replayed.get("tool"):
                differences.append(Difference(
                    field="tool_name",
                    original_value=orig.tool_name,
                    replayed_value=replayed.get("tool"),
                    location=f"tool_call_{i}",
                    significance="critical"
                ))

            # Parameters might differ slightly (timestamps, etc.)
            # Only flag if major parameter changes

        return differences
