"""
Core agent classes and interfaces.

Implements the base agent abstraction with role-based specialization.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List
import logging

from .state import StateManager
from ia_modules.telemetry.integration import get_agent_telemetry


@dataclass
class AgentRole:
    """
    Defines an agent's specialized role and capabilities.

    Attributes:
        name: Unique role identifier (e.g., "planner", "researcher")
        description: Human-readable description of role
        allowed_tools: List of tool names this agent can use
        system_prompt: System prompt defining agent behavior
        max_iterations: Maximum iterations for feedback loops
        metadata: Additional role configuration
    """
    name: str
    description: str
    allowed_tools: List[str] = field(default_factory=list)
    system_prompt: str = ""
    max_iterations: int = 10
    metadata: Dict[str, Any] = field(default_factory=dict)


class BaseAgent(ABC):
    """
    Base class for all specialized agents.

    Agents are single-purpose components in a multi-agent workflow.
    They read from and write to a centralized state, and perform
    specific tasks based on their role.

    Example:
        >>> class MyAgent(BaseAgent):
        ...     async def execute(self, input_data):
        ...         # Read from state
        ...         value = await self.read_state("key")
        ...
        ...         # Do work
        ...         result = process(value)
        ...
        ...         # Write to state
        ...         await self.write_state("result", result)
        ...
        ...         return {"status": "success"}
    """

    def __init__(self, role: AgentRole, state_manager: "StateManager",
                 enable_telemetry: bool = True):
        """
        Initialize agent.

        Args:
            role: Agent's role definition
            state_manager: Centralized state for agent communication
            enable_telemetry: Whether to enable agent telemetry
        """
        self.role = role
        self.state = state_manager
        self.logger = logging.getLogger(f"Agent.{role.name}")
        self._iteration_count = 0

        # Telemetry
        self.enable_telemetry = enable_telemetry
        self._telemetry = get_agent_telemetry() if enable_telemetry else None

    @abstractmethod
    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute agent's specialized task.

        Agents should:
        1. Read necessary data from state
        2. Perform their specialized task
        3. Write results back to state
        4. Return execution summary

        Args:
            input_data: Input parameters for this execution

        Returns:
            Dictionary with execution results and metadata

        Example:
            return {"status": "success", "items_processed": 5}
        """
        pass

    async def read_state(self, key: str, default: Any = None) -> Any:
        """
        Read value from centralized state.

        Args:
            key: State key to read
            default: Default value if key doesn't exist

        Returns:
            Value from state or default
        """
        if self._telemetry:
            self._telemetry.record_state_operation(self.role.name, "read")
        return await self.state.get(key, default)

    async def write_state(self, key: str, value: Any) -> None:
        """
        Write value to centralized state.

        Args:
            key: State key to write
            value: Value to store
        """
        if self._telemetry:
            self._telemetry.record_state_operation(self.role.name, "write")
        await self.state.set(key, value)

    async def get_state_snapshot(self) -> Dict[str, Any]:
        """
        Get immutable snapshot of entire state.

        Returns:
            Copy of current state
        """
        if self._telemetry:
            self._telemetry.record_state_operation(self.role.name, "snapshot")
        return await self.state.snapshot()

    def increment_iteration(self) -> int:
        """
        Increment and return iteration count.

        Used for tracking feedback loops.

        Returns:
            Current iteration number
        """
        self._iteration_count += 1
        if self._telemetry:
            self._telemetry.record_iteration(self.role.name)
        return self._iteration_count

    def reset_iterations(self) -> None:
        """Reset iteration counter."""
        self._iteration_count = 0

    @property
    def iteration_count(self) -> int:
        """Current iteration count."""
        return self._iteration_count

    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(role={self.role.name})>"
