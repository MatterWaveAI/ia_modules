"""
Unit tests for mode enforcer.

Tests ModeEnforcer, AgentMode, and ModeViolation.
"""

from ia_modules.reliability.mode_enforcer import (
    AgentMode,
    ModeViolation,
    ModeEnforcer
)


class TestAgentMode:
    """Test AgentMode enum."""

    def test_explore_mode(self):
        """EXPLORE mode exists."""
        assert AgentMode.EXPLORE.value == "explore"

    def test_execute_mode(self):
        """EXECUTE mode exists."""
        assert AgentMode.EXECUTE.value == "execute"

    def test_escalate_mode(self):
        """ESCALATE mode exists."""
        assert AgentMode.ESCALATE.value == "escalate"


class TestModeViolation:
    """Test ModeViolation dataclass."""

    def test_violation_creation(self):
        """ModeViolation can be created."""
        violation = ModeViolation(
            agent_name="planner",
            declared_mode=AgentMode.EXPLORE,
            attempted_action="write_file",
            violation_type="write_in_explore",
            details="Tried to write in explore mode"
        )

        assert violation.agent_name == "planner"
        assert violation.declared_mode == AgentMode.EXPLORE
        assert violation.violation_type == "write_in_explore"


class TestModeEnforcer:
    """Test ModeEnforcer class."""

    def test_enforcer_creation(self):
        """ModeEnforcer can be created."""
        enforcer = ModeEnforcer()

        assert enforcer.agent_modes == {}
        assert enforcer.violations == []

    def test_set_mode(self):
        """Can set agent mode."""
        enforcer = ModeEnforcer()

        enforcer.set_mode("planner", AgentMode.EXPLORE)

        assert enforcer.get_mode("planner") == AgentMode.EXPLORE

    def test_get_mode_not_set(self):
        """get_mode returns None when not set."""
        enforcer = ModeEnforcer()

        assert enforcer.get_mode("unknown") is None

    def test_can_execute_explore_read_allowed(self):
        """Can execute read actions in EXPLORE mode."""
        enforcer = ModeEnforcer()
        enforcer.set_mode("researcher", AgentMode.EXPLORE)

        assert enforcer.can_execute("researcher", "read_file") is True
        assert enforcer.can_execute("researcher", "search_web") is True
        assert enforcer.can_execute("researcher", "query_database") is True

    def test_can_execute_explore_write_blocked(self):
        """Cannot execute write actions in EXPLORE mode."""
        enforcer = ModeEnforcer()
        enforcer.set_mode("researcher", AgentMode.EXPLORE)

        assert enforcer.can_execute("researcher", "write_file") is False
        assert enforcer.can_execute("researcher", "update_database") is False
        assert enforcer.can_execute("researcher", "delete_record") is False

    def test_can_execute_explore_records_violation(self):
        """Write action in EXPLORE mode records violation."""
        enforcer = ModeEnforcer()
        enforcer.set_mode("researcher", AgentMode.EXPLORE)

        enforcer.can_execute("researcher", "write_file")

        assert len(enforcer.violations) == 1
        assert enforcer.violations[0].violation_type == "write_in_explore"

    def test_can_execute_execute_all_allowed(self):
        """Can execute any action in EXECUTE mode."""
        enforcer = ModeEnforcer()
        enforcer.set_mode("coder", AgentMode.EXECUTE)

        assert enforcer.can_execute("coder", "read_file") is True
        assert enforcer.can_execute("coder", "write_file") is True
        assert enforcer.can_execute("coder", "delete_file") is True

    def test_can_execute_escalate_no_approval(self):
        """Cannot execute in ESCALATE mode without approval."""
        enforcer = ModeEnforcer()
        enforcer.set_mode("agent", AgentMode.ESCALATE)

        assert enforcer.can_execute("agent", "any_action") is False

    def test_can_execute_escalate_with_approval(self):
        """Can execute in ESCALATE mode with approval."""
        enforcer = ModeEnforcer()
        enforcer.set_mode("agent", AgentMode.ESCALATE)
        enforcer.grant_approval("agent")

        assert enforcer.can_execute("agent", "any_action") is True

    def test_require_approval(self):
        """Can require approval for agent."""
        enforcer = ModeEnforcer()

        enforcer.require_approval("agent", "Need to delete database")

        assert enforcer.get_mode("agent") == AgentMode.ESCALATE

    def test_grant_approval(self):
        """Can grant approval."""
        enforcer = ModeEnforcer()
        enforcer.set_mode("agent", AgentMode.ESCALATE)

        enforcer.grant_approval("agent")

        assert enforcer.can_execute("agent", "action") is True

    def test_revoke_approval(self):
        """Can revoke approval."""
        enforcer = ModeEnforcer()
        enforcer.set_mode("agent", AgentMode.ESCALATE)
        enforcer.grant_approval("agent")

        enforcer.revoke_approval("agent")

        assert enforcer.can_execute("agent", "action") is False

    def test_validate_mode_match(self):
        """validate_mode returns True when modes match."""
        enforcer = ModeEnforcer()

        result = enforcer.validate_mode(
            "agent",
            declared_mode=AgentMode.EXPLORE,
            actual_mode=AgentMode.EXPLORE
        )

        assert result is True
        assert len(enforcer.violations) == 0

    def test_validate_mode_mismatch(self):
        """validate_mode returns False when modes don't match."""
        enforcer = ModeEnforcer()

        result = enforcer.validate_mode(
            "agent",
            declared_mode=AgentMode.EXPLORE,
            actual_mode=AgentMode.EXECUTE
        )

        assert result is False
        assert len(enforcer.violations) == 1
        assert enforcer.violations[0].violation_type == "mode_mismatch"

    def test_get_violations_all(self):
        """Can get all violations."""
        enforcer = ModeEnforcer()
        enforcer.set_mode("agent1", AgentMode.EXPLORE)
        enforcer.set_mode("agent2", AgentMode.EXPLORE)

        enforcer.can_execute("agent1", "write_file")
        enforcer.can_execute("agent2", "write_file")

        violations = enforcer.get_violations()
        assert len(violations) == 2

    def test_get_violations_by_agent(self):
        """Can get violations for specific agent."""
        enforcer = ModeEnforcer()
        enforcer.set_mode("agent1", AgentMode.EXPLORE)
        enforcer.set_mode("agent2", AgentMode.EXPLORE)

        enforcer.can_execute("agent1", "write_file")
        enforcer.can_execute("agent2", "write_file")

        violations = enforcer.get_violations(agent_name="agent1")
        assert len(violations) == 1
        assert violations[0].agent_name == "agent1"

    def test_get_violation_count(self):
        """Can get violation count."""
        enforcer = ModeEnforcer()
        enforcer.set_mode("agent", AgentMode.EXPLORE)

        enforcer.can_execute("agent", "write_file")
        enforcer.can_execute("agent", "delete_file")

        assert enforcer.get_violation_count() == 2
        assert enforcer.get_violation_count(agent_name="agent") == 2

    def test_clear_violations_all(self):
        """Can clear all violations."""
        enforcer = ModeEnforcer()
        enforcer.set_mode("agent", AgentMode.EXPLORE)
        enforcer.can_execute("agent", "write_file")

        enforcer.clear_violations()

        assert len(enforcer.violations) == 0

    def test_clear_violations_by_agent(self):
        """Can clear violations for specific agent."""
        enforcer = ModeEnforcer()
        enforcer.set_mode("agent1", AgentMode.EXPLORE)
        enforcer.set_mode("agent2", AgentMode.EXPLORE)

        enforcer.can_execute("agent1", "write_file")
        enforcer.can_execute("agent2", "write_file")

        enforcer.clear_violations(agent_name="agent1")

        assert len(enforcer.violations) == 1
        assert enforcer.violations[0].agent_name == "agent2"

    def test_tool_name_read_detection(self):
        """Tool name is used to detect read operations."""
        enforcer = ModeEnforcer()
        enforcer.set_mode("agent", AgentMode.EXPLORE)

        # Should allow because tool is read-only
        assert enforcer.can_execute("agent", "process_data", tool_name="search_api") is True

    def test_tool_name_write_detection(self):
        """Tool name is used to detect write operations."""
        enforcer = ModeEnforcer()
        enforcer.set_mode("agent", AgentMode.EXPLORE)

        # Should block because tool is write
        assert enforcer.can_execute("agent", "process_data", tool_name="write_database") is False

    def test_no_mode_set_allows_by_default(self):
        """Actions allowed when no mode is set."""
        enforcer = ModeEnforcer()

        # Should allow but log warning
        assert enforcer.can_execute("agent", "write_file") is True
