"""
Mode Enforcer

Enforces agent modes (explore/execute/escalate) to ensure predictable behavior.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Callable
from enum import Enum
import logging


class AgentMode(Enum):
    """Agent operating modes."""
    EXPLORE = "explore"      # Research and information gathering (read-only)
    EXECUTE = "execute"      # Take concrete actions (read-write)
    ESCALATE = "escalate"    # Request human intervention


@dataclass
class ModeViolation:
    """Record of a mode violation."""
    agent_name: str
    declared_mode: AgentMode
    attempted_action: str
    violation_type: str  # "write_in_explore", "no_approval", "mode_mismatch"
    details: str


class ModeEnforcer:
    """
    Enforce agent modes to ensure predictable behavior.

    Modes:
    - EXPLORE: Read-only operations, cannot modify state or external systems
    - EXECUTE: Can modify state and systems, requires validation
    - ESCALATE: Must get human approval before proceeding

    Example:
        >>> enforcer = ModeEnforcer()
        >>>
        >>> # Declare agent mode
        >>> enforcer.set_mode("planner", AgentMode.EXPLORE)
        >>>
        >>> # Check if action is allowed
        >>> if enforcer.can_execute("planner", "write_file"):
        ...     # Action allowed
        ...     pass
        ... else:
        ...     # Action blocked
        ...     raise ModeViolationError()
        >>>
        >>> # Get violations
        >>> violations = enforcer.get_violations()
    """

    def __init__(self):
        """Initialize mode enforcer."""
        self.agent_modes: Dict[str, AgentMode] = {}
        self.violations: List[ModeViolation] = []
        self.read_only_tools: List[str] = [
            "search", "lookup", "read", "get", "fetch", "query", "analyze"
        ]
        self.write_tools: List[str] = [
            "write", "update", "delete", "create", "modify", "execute", "run"
        ]
        self.approval_callbacks: Dict[str, Callable] = {}
        self.logger = logging.getLogger("ModeEnforcer")

    def set_mode(self, agent_name: str, mode: AgentMode):
        """
        Set agent's operating mode.

        Args:
            agent_name: Name of the agent
            mode: Operating mode
        """
        self.agent_modes[agent_name] = mode
        self.logger.info(f"Agent '{agent_name}' mode set to {mode.value}")

    def get_mode(self, agent_name: str) -> Optional[AgentMode]:
        """
        Get agent's current mode.

        Args:
            agent_name: Name of the agent

        Returns:
            Current mode or None if not set
        """
        return self.agent_modes.get(agent_name)

    def can_execute(
        self,
        agent_name: str,
        action: str,
        tool_name: Optional[str] = None
    ) -> bool:
        """
        Check if agent can execute an action in current mode.

        Args:
            agent_name: Name of the agent
            action: Action to execute (e.g., "write_file", "read_data")
            tool_name: Optional tool name for more specific checking

        Returns:
            True if action is allowed, False otherwise
        """
        mode = self.get_mode(agent_name)

        if mode is None:
            # No mode set - allow by default but log warning
            self.logger.warning(f"Agent '{agent_name}' has no mode set, allowing action '{action}'")
            return True

        # Check based on mode
        if mode == AgentMode.EXPLORE:
            # Only read-only operations allowed
            if self._is_write_action(action, tool_name):
                self._record_violation(
                    agent_name=agent_name,
                    declared_mode=mode,
                    attempted_action=action,
                    violation_type="write_in_explore",
                    details=f"Attempted write operation '{action}' in EXPLORE mode"
                )
                return False
            return True

        elif mode == AgentMode.EXECUTE:
            # All operations allowed (validation should happen elsewhere)
            return True

        elif mode == AgentMode.ESCALATE:
            # Must have human approval
            if not self._has_approval(agent_name):
                self._record_violation(
                    agent_name=agent_name,
                    declared_mode=mode,
                    attempted_action=action,
                    violation_type="no_approval",
                    details=f"Attempted action '{action}' in ESCALATE mode without approval"
                )
                return False
            return True

        return True

    def require_approval(
        self,
        agent_name: str,
        request_message: str,
        approval_callback: Optional[Callable] = None
    ):
        """
        Require human approval for agent to proceed.

        Args:
            agent_name: Name of the agent
            request_message: Message explaining what needs approval
            approval_callback: Optional callback to check approval status
        """
        self.set_mode(agent_name, AgentMode.ESCALATE)

        if approval_callback:
            self.approval_callbacks[agent_name] = approval_callback

        self.logger.info(f"Agent '{agent_name}' requires approval: {request_message}")

    def grant_approval(self, agent_name: str):
        """
        Grant approval for agent to proceed.

        Args:
            agent_name: Name of the agent
        """
        # Set callback that always returns True
        self.approval_callbacks[agent_name] = lambda: True
        self.logger.info(f"Approval granted for agent '{agent_name}'")

    def revoke_approval(self, agent_name: str):
        """
        Revoke approval for agent.

        Args:
            agent_name: Name of the agent
        """
        if agent_name in self.approval_callbacks:
            del self.approval_callbacks[agent_name]
        self.logger.info(f"Approval revoked for agent '{agent_name}'")

    def validate_mode(
        self,
        agent_name: str,
        declared_mode: AgentMode,
        actual_mode: AgentMode
    ) -> bool:
        """
        Validate that agent's actual mode matches declared mode.

        Args:
            agent_name: Name of the agent
            declared_mode: What agent claims its mode is
            actual_mode: What mode agent is actually operating in

        Returns:
            True if modes match, False otherwise
        """
        if declared_mode != actual_mode:
            self._record_violation(
                agent_name=agent_name,
                declared_mode=declared_mode,
                attempted_action="mode_declaration",
                violation_type="mode_mismatch",
                details=f"Declared {declared_mode.value} but operating in {actual_mode.value}"
            )
            return False

        return True

    def get_violations(
        self,
        agent_name: Optional[str] = None
    ) -> List[ModeViolation]:
        """
        Get mode violations.

        Args:
            agent_name: Filter by agent name (optional)

        Returns:
            List of violations
        """
        if agent_name:
            return [v for v in self.violations if v.agent_name == agent_name]
        return self.violations.copy()

    def get_violation_count(self, agent_name: Optional[str] = None) -> int:
        """
        Get count of violations.

        Args:
            agent_name: Filter by agent name (optional)

        Returns:
            Number of violations
        """
        return len(self.get_violations(agent_name=agent_name))

    def clear_violations(self, agent_name: Optional[str] = None):
        """
        Clear violations.

        Args:
            agent_name: Clear only for this agent (optional, clears all if None)
        """
        if agent_name:
            self.violations = [v for v in self.violations if v.agent_name != agent_name]
        else:
            self.violations.clear()

    def _is_write_action(self, action: str, tool_name: Optional[str] = None) -> bool:
        """
        Check if action is a write operation.

        Args:
            action: Action name
            tool_name: Optional tool name

        Returns:
            True if write operation, False otherwise
        """
        action_lower = action.lower()

        # Check tool name if provided
        if tool_name:
            tool_lower = tool_name.lower()
            if any(write_word in tool_lower for write_word in self.write_tools):
                return True
            if any(read_word in tool_lower for read_word in self.read_only_tools):
                return False

        # Check action name
        if any(write_word in action_lower for write_word in self.write_tools):
            return True

        return False

    def _has_approval(self, agent_name: str) -> bool:
        """
        Check if agent has approval.

        Args:
            agent_name: Name of the agent

        Returns:
            True if approved, False otherwise
        """
        callback = self.approval_callbacks.get(agent_name)
        if callback is None:
            return False

        try:
            return callback()
        except Exception as e:
            self.logger.error(f"Error checking approval for {agent_name}: {e}")
            return False

    def _record_violation(
        self,
        agent_name: str,
        declared_mode: AgentMode,
        attempted_action: str,
        violation_type: str,
        details: str
    ):
        """Record a mode violation."""
        violation = ModeViolation(
            agent_name=agent_name,
            declared_mode=declared_mode,
            attempted_action=attempted_action,
            violation_type=violation_type,
            details=details
        )

        self.violations.append(violation)
        self.logger.warning(
            f"Mode violation: {agent_name} ({declared_mode.value}) - {violation_type}: {details}"
        )
