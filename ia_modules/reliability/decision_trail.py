"""
Decision Trail System

Provides unified API to reconstruct complete decision history for agent workflows.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Literal
from datetime import datetime, timezone
import logging


@dataclass
class Evidence:
    """
    Verifiable fact vs agent claim.

    Evidence is categorized by confidence level:
    - "verified": From external tools (API calls, database reads)
    - "claimed": From agent outputs (LLM generations)
    - "inferred": Derived from other evidence

    Example:
        >>> # Tool result = verified
        >>> Evidence(
        ...     type="tool_result",
        ...     source="search_api",
        ...     content={"results": [...]},
        ...     confidence="verified"
        ... )
        >>>
        >>> # Agent state write = claimed
        >>> Evidence(
        ...     type="agent_claim",
        ...     source="planner_agent",
        ...     content={"plan": ["step1", "step2"]},
        ...     confidence="claimed"
        ... )
    """
    type: str  # "tool_result", "database_read", "api_response", "user_input", "agent_claim"
    source: str  # Tool name, agent name, API endpoint, etc.
    content: Any  # The actual evidence data
    timestamp: str  # ISO 8601 timestamp
    confidence: Literal["verified", "claimed", "inferred"]
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StepRecord:
    """
    Record of a single step in agent execution.

    Captures:
    - What agent ran
    - What it received as input
    - What it produced as output
    - Whether it succeeded
    - How long it took
    - How many retries were needed
    """
    agent: str
    step_index: int
    timestamp: str
    input_data: Dict[str, Any]
    output_data: Dict[str, Any]
    success: bool
    error: Optional[str] = None
    duration_ms: int = 0
    retries: int = 0
    state_before: Dict[str, Any] = field(default_factory=dict)
    state_after: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ToolCall:
    """Record of a tool execution."""
    tool_name: str
    parameters: Dict[str, Any]
    result: Any
    success: bool
    timestamp: str
    duration_ms: int = 0
    error: Optional[str] = None


@dataclass
class StateDelta:
    """
    Record of a state change.

    Tracks what changed, when, and by whom.
    """
    key: str
    old_value: Any
    new_value: Any
    changed_by: str  # Agent name
    timestamp: str
    version: int  # State version number


@dataclass
class DecisionTrail:
    """
    Complete record of an agent decision.

    This is the unified representation that answers:
    - What was the goal?
    - What did the agents do?
    - What evidence did they collect?
    - What was the outcome?
    - How long did it take?
    - How much did it cost?

    Example:
        >>> trail = await builder.build_trail("thread-123")
        >>> print(f"Goal: {trail.goal}")
        >>> print(f"Success: {trail.success}")
        >>> print(f"Steps: {len(trail.steps_taken)}")
        >>> print(f"Evidence: {len(trail.evidence)}")
    """

    # Identity
    thread_id: str
    checkpoint_id: str
    workflow_name: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    # Context
    goal: str = ""  # What was the agent trying to do?
    input_data: Dict[str, Any] = field(default_factory=dict)

    # Execution
    plan: List[str] = field(default_factory=list)  # Planned steps
    steps_taken: List[StepRecord] = field(default_factory=list)  # Actual steps
    execution_path: List[str] = field(default_factory=list)  # Agent names in order

    # Evidence
    tool_calls: List[ToolCall] = field(default_factory=list)
    state_deltas: List[StateDelta] = field(default_factory=list)
    evidence: List[Evidence] = field(default_factory=list)

    # Outcome
    outcome: Dict[str, Any] = field(default_factory=dict)
    success: bool = False
    confidence: Optional[float] = None  # 0.0 - 1.0

    # Metrics
    duration_ms: int = 0
    tokens_used: Optional[int] = None
    cost_usd: Optional[float] = None

    # Metadata
    metadata: Dict[str, Any] = field(default_factory=dict)


class DecisionTrailBuilder:
    """
    Build decision trails from state/checkpoint/logs.

    Assembles complete decision history by combining:
    - State history from StateManager
    - Checkpoint metadata
    - Tool execution logs from ToolRegistry
    - Agent execution path from Orchestrator

    Example:
        >>> builder = DecisionTrailBuilder(state_manager, tool_registry)
        >>> trail = await builder.build_trail("thread-123")
        >>> explanation = await builder.explain_decision(trail)
    """

    def __init__(
        self,
        state_manager: Optional[Any] = None,
        tool_registry: Optional[Any] = None,
        checkpointer: Optional[Any] = None
    ):
        """
        Initialize trail builder.

        Args:
            state_manager: StateManager for state history
            tool_registry: ToolRegistry for tool execution logs
            checkpointer: Checkpointer for checkpoint metadata
        """
        self.state_manager = state_manager
        self.tool_registry = tool_registry
        self.checkpointer = checkpointer
        self.logger = logging.getLogger("DecisionTrailBuilder")

    async def build_trail(
        self,
        thread_id: str,
        checkpoint_id: Optional[str] = None,
        include_evidence: bool = True
    ) -> DecisionTrail:
        """
        Reconstruct complete decision trail.

        Args:
            thread_id: Workflow thread ID
            checkpoint_id: Specific checkpoint (or latest if None)
            include_evidence: Whether to extract evidence from tool calls

        Returns:
            Complete DecisionTrail with all history

        Example:
            >>> trail = await builder.build_trail("thread-123")
            >>> print(f"Took {trail.duration_ms}ms")
            >>> print(f"Used {len(trail.tool_calls)} tools")
        """
        start_time = datetime.now(timezone.utc)

        # Get checkpoint metadata
        checkpoint = None
        if self.checkpointer:
            if checkpoint_id:
                checkpoint = await self.checkpointer.get_checkpoint(thread_id, checkpoint_id)
            else:
                checkpoint = await self.checkpointer.load_checkpoint(thread_id)

        # Initialize trail
        trail = DecisionTrail(
            thread_id=thread_id,
            checkpoint_id=checkpoint_id or (checkpoint.checkpoint_id if checkpoint else "unknown"),
            timestamp=start_time.isoformat()
        )

        # Extract goal and input from checkpoint metadata
        if checkpoint and checkpoint.metadata:
            trail.goal = checkpoint.metadata.get("goal", "")
            trail.input_data = checkpoint.metadata.get("input_data", {})
            trail.execution_path = checkpoint.metadata.get("execution_path", [])

        # Get state history
        if self.state_manager:
            state_history = self.state_manager._versions  # Access version history

            # Build state deltas
            for i, version in enumerate(state_history):
                if i == 0:
                    continue  # Skip first version (no delta)

                prev_version = state_history[i - 1]

                # Find changed keys
                for key in set(list(version.keys()) + list(prev_version.keys())):
                    old_val = prev_version.get(key)
                    new_val = version.get(key)

                    if old_val != new_val:
                        trail.state_deltas.append(StateDelta(
                            key=key,
                            old_value=old_val,
                            new_value=new_val,
                            changed_by="unknown",  # Would need to track this
                            timestamp=start_time.isoformat(),
                            version=i
                        ))

            # Get final state as outcome
            if self.state_manager._state:
                trail.outcome = dict(self.state_manager._state)

        # Get tool execution logs
        if self.tool_registry and hasattr(self.tool_registry, '_execution_log'):
            for log_entry in self.tool_registry._execution_log:
                tool_call = ToolCall(
                    tool_name=log_entry["tool"],
                    parameters=log_entry.get("parameters", {}),
                    result=log_entry.get("result"),
                    success=log_entry["success"],
                    timestamp=log_entry["timestamp"],
                    duration_ms=int(log_entry.get("duration", 0) * 1000),
                    error=log_entry.get("error")
                )
                trail.tool_calls.append(tool_call)

                # Extract evidence from tool calls
                if include_evidence and tool_call.success:
                    evidence = Evidence(
                        type="tool_result",
                        source=tool_call.tool_name,
                        content=tool_call.result,
                        timestamp=tool_call.timestamp,
                        confidence="verified"
                    )
                    trail.evidence.append(evidence)

        # Calculate duration
        end_time = datetime.now(timezone.utc)
        trail.duration_ms = int((end_time - start_time).total_seconds() * 1000)

        # Determine success (if all tool calls succeeded)
        if trail.tool_calls:
            trail.success = all(tc.success for tc in trail.tool_calls)
        else:
            trail.success = True  # No tools = assumed success

        return trail

    async def explain_decision(
        self,
        trail: DecisionTrail,
        include_evidence: bool = True,
        include_state_deltas: bool = False
    ) -> str:
        """
        Generate human-readable explanation of decision.

        Args:
            trail: DecisionTrail to explain
            include_evidence: Include evidence details
            include_state_deltas: Include state change details

        Returns:
            Markdown-formatted explanation

        Example:
            >>> explanation = await builder.explain_decision(trail)
            >>> print(explanation)
        """
        lines = []

        # Header
        lines.append(f"# Decision Trail: {trail.thread_id}")
        lines.append(f"**Timestamp**: {trail.timestamp}")
        lines.append(f"**Checkpoint**: {trail.checkpoint_id}")
        lines.append(f"**Success**: {trail.success}")
        lines.append("")

        # Goal
        if trail.goal:
            lines.append("## Goal")
            lines.append(trail.goal)
            lines.append("")

        # Input
        if trail.input_data:
            lines.append("## Input Data")
            for key, value in trail.input_data.items():
                lines.append(f"- **{key}**: {value}")
            lines.append("")

        # Execution path
        if trail.execution_path:
            lines.append("## Execution Path")
            for i, agent in enumerate(trail.execution_path, 1):
                lines.append(f"{i}. {agent}")
            lines.append("")

        # Steps taken
        if trail.steps_taken:
            lines.append("## Steps Executed")
            for step in trail.steps_taken:
                status = "✓" if step.success else "✗"
                lines.append(f"{status} **{step.agent}** (step {step.step_index})")
                if step.error:
                    lines.append(f"  - Error: {step.error}")
                if step.retries > 0:
                    lines.append(f"  - Retries: {step.retries}")
            lines.append("")

        # Tool calls
        if trail.tool_calls:
            lines.append(f"## Tool Calls ({len(trail.tool_calls)} total)")
            for tc in trail.tool_calls:
                status = "✓" if tc.success else "✗"
                lines.append(f"{status} **{tc.tool_name}**")
                lines.append(f"  - Parameters: {tc.parameters}")
                if tc.success:
                    lines.append(f"  - Result: {tc.result}")
                else:
                    lines.append(f"  - Error: {tc.error}")
                lines.append(f"  - Duration: {tc.duration_ms}ms")
            lines.append("")

        # Evidence
        if include_evidence and trail.evidence:
            lines.append(f"## Evidence ({len(trail.evidence)} items)")
            verified = [e for e in trail.evidence if e.confidence == "verified"]
            claimed = [e for e in trail.evidence if e.confidence == "claimed"]

            if verified:
                lines.append(f"### Verified Facts ({len(verified)})")
                for e in verified:
                    lines.append(f"- **{e.source}**: {e.type}")

            if claimed:
                lines.append(f"### Agent Claims ({len(claimed)})")
                for e in claimed:
                    lines.append(f"- **{e.source}**: {e.type}")
            lines.append("")

        # State deltas
        if include_state_deltas and trail.state_deltas:
            lines.append(f"## State Changes ({len(trail.state_deltas)})")
            for delta in trail.state_deltas:
                lines.append(f"- **{delta.key}**: {delta.old_value} → {delta.new_value}")
                lines.append(f"  - Changed by: {delta.changed_by}")
                lines.append(f"  - Version: {delta.version}")
            lines.append("")

        # Outcome
        lines.append("## Outcome")
        for key, value in trail.outcome.items():
            lines.append(f"- **{key}**: {value}")
        lines.append("")

        # Metrics
        lines.append("## Metrics")
        lines.append(f"- Duration: {trail.duration_ms}ms")
        if trail.tokens_used:
            lines.append(f"- Tokens: {trail.tokens_used}")
        if trail.cost_usd:
            lines.append(f"- Cost: ${trail.cost_usd:.4f}")

        return "\n".join(lines)
