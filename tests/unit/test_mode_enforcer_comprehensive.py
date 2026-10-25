"""Comprehensive tests for reliability.mode_enforcer module"""

from ia_modules.reliability.mode_enforcer import (
    AgentMode,
    ModeViolation,
    ModeEnforcer
)


class TestAgentMode:
    """Test AgentMode enum"""

    def test_explore_mode(self):
        """Test EXPLORE mode"""
        assert AgentMode.EXPLORE.value == "explore"

    def test_execute_mode(self):
        """Test EXECUTE mode"""
        assert AgentMode.EXECUTE.value == "execute"

    def test_escalate_mode(self):
        """Test ESCALATE mode"""
        assert AgentMode.ESCALATE.value == "escalate"


class TestModeViolation:
    """Test ModeViolation dataclass"""

    def test_init(self):
        """Test violation creation"""
        violation = ModeViolation(
            agent_name="planner",
            declared_mode=AgentMode.EXPLORE,
            attempted_action="write_file",
            violation_type="write_in_explore",
            details="Attempted write in EXPLORE mode"
        )

        assert violation.agent_name == "planner"
        assert violation.declared_mode == AgentMode.EXPLORE
        assert violation.attempted_action == "write_file"
        assert violation.violation_type == "write_in_explore"


class TestModeEnforcer:
    """Test ModeEnforcer class"""

    def test_init(self):
        """Test enforcer initialization"""
        enforcer = ModeEnforcer()
        assert len(enforcer.agent_modes) == 0
        assert len(enforcer.violations) == 0
        assert len(enforcer.read_only_tools) > 0
        assert len(enforcer.write_tools) > 0

    def test_set_mode(self):
        """Test setting agent mode"""
        enforcer = ModeEnforcer()
        enforcer.set_mode("planner", AgentMode.EXPLORE)

        assert enforcer.agent_modes["planner"] == AgentMode.EXPLORE

    def test_get_mode(self):
        """Test getting agent mode"""
        enforcer = ModeEnforcer()
        enforcer.set_mode("planner", AgentMode.EXECUTE)

        mode = enforcer.get_mode("planner")
        assert mode == AgentMode.EXECUTE

    def test_get_mode_not_set(self):
        """Test getting mode for agent without mode"""
        enforcer = ModeEnforcer()
        mode = enforcer.get_mode("unknown")
        assert mode is None

    def test_can_execute_no_mode_set(self):
        """Test allowing action when no mode set"""
        enforcer = ModeEnforcer()
        # Should allow by default with warning
        result = enforcer.can_execute("planner", "write_file")
        assert result is True

    def test_can_execute_explore_read_allowed(self):
        """Test EXPLORE mode allows read operations"""
        enforcer = ModeEnforcer()
        enforcer.set_mode("planner", AgentMode.EXPLORE)

        result = enforcer.can_execute("planner", "search_database")
        assert result is True

    def test_can_execute_explore_write_blocked(self):
        """Test EXPLORE mode blocks write operations"""
        enforcer = ModeEnforcer()
        enforcer.set_mode("planner", AgentMode.EXPLORE)

        result = enforcer.can_execute("planner", "write_file")
        assert result is False
        assert len(enforcer.violations) == 1

    def test_can_execute_execute_mode_allows_all(self):
        """Test EXECUTE mode allows all operations"""
        enforcer = ModeEnforcer()
        enforcer.set_mode("coder", AgentMode.EXECUTE)

        assert enforcer.can_execute("coder", "write_file") is True
        assert enforcer.can_execute("coder", "read_file") is True
        assert enforcer.can_execute("coder", "delete_file") is True

    def test_can_execute_escalate_without_approval(self):
        """Test ESCALATE mode blocks without approval"""
        enforcer = ModeEnforcer()
        enforcer.set_mode("planner", AgentMode.ESCALATE)

        result = enforcer.can_execute("planner", "write_file")
        assert result is False
        assert len(enforcer.violations) == 1

    def test_can_execute_escalate_with_approval(self):
        """Test ESCALATE mode allows with approval"""
        enforcer = ModeEnforcer()
        enforcer.set_mode("planner", AgentMode.ESCALATE)
        enforcer.grant_approval("planner")

        result = enforcer.can_execute("planner", "write_file")
        assert result is True

    def test_can_execute_with_tool_name(self):
        """Test action checking with tool name"""
        enforcer = ModeEnforcer()
        enforcer.set_mode("planner", AgentMode.EXPLORE)

        # Read tool should be allowed
        result = enforcer.can_execute("planner", "process", tool_name="read_database")
        assert result is True

        # Write tool should be blocked
        result = enforcer.can_execute("planner", "process", tool_name="write_database")
        assert result is False

    def test_require_approval(self):
        """Test requiring approval"""
        enforcer = ModeEnforcer()

        enforcer.require_approval("planner", "Need approval to proceed")

        assert enforcer.get_mode("planner") == AgentMode.ESCALATE

    def test_require_approval_with_callback(self):
        """Test requiring approval with callback"""
        enforcer = ModeEnforcer()

        def approval_check():
            return True

        enforcer.require_approval("planner", "Need approval", approval_check)

        assert "planner" in enforcer.approval_callbacks

    def test_grant_approval(self):
        """Test granting approval"""
        enforcer = ModeEnforcer()
        enforcer.set_mode("planner", AgentMode.ESCALATE)

        enforcer.grant_approval("planner")

        assert enforcer.can_execute("planner", "write_file") is True

    def test_revoke_approval(self):
        """Test revoking approval"""
        enforcer = ModeEnforcer()
        enforcer.set_mode("planner", AgentMode.ESCALATE)
        enforcer.grant_approval("planner")

        enforcer.revoke_approval("planner")

        assert enforcer.can_execute("planner", "write_file") is False

    def test_validate_mode_matching(self):
        """Test validating matching modes"""
        enforcer = ModeEnforcer()

        result = enforcer.validate_mode(
            "planner",
            AgentMode.EXPLORE,
            AgentMode.EXPLORE
        )

        assert result is True
        assert len(enforcer.violations) == 0

    def test_validate_mode_mismatch(self):
        """Test validating mismatched modes"""
        enforcer = ModeEnforcer()

        result = enforcer.validate_mode(
            "planner",
            AgentMode.EXPLORE,
            AgentMode.EXECUTE
        )

        assert result is False
        assert len(enforcer.violations) == 1
        assert enforcer.violations[0].violation_type == "mode_mismatch"

    def test_get_violations_all(self):
        """Test getting all violations"""
        enforcer = ModeEnforcer()
        enforcer.set_mode("planner", AgentMode.EXPLORE)

        enforcer.can_execute("planner", "write_file")
        enforcer.can_execute("planner", "delete_file")

        violations = enforcer.get_violations()
        assert len(violations) == 2

    def test_get_violations_by_agent(self):
        """Test filtering violations by agent"""
        enforcer = ModeEnforcer()
        enforcer.set_mode("planner", AgentMode.EXPLORE)
        enforcer.set_mode("coder", AgentMode.EXPLORE)

        enforcer.can_execute("planner", "write_file")
        enforcer.can_execute("coder", "write_file")
        enforcer.can_execute("planner", "delete_file")

        violations = enforcer.get_violations(agent_name="planner")
        assert len(violations) == 2
        assert all(v.agent_name == "planner" for v in violations)

    def test_get_violation_count(self):
        """Test getting violation count"""
        enforcer = ModeEnforcer()
        enforcer.set_mode("planner", AgentMode.EXPLORE)

        enforcer.can_execute("planner", "write_file")
        enforcer.can_execute("planner", "delete_file")

        count = enforcer.get_violation_count()
        assert count == 2

    def test_get_violation_count_by_agent(self):
        """Test getting violation count by agent"""
        enforcer = ModeEnforcer()
        enforcer.set_mode("planner", AgentMode.EXPLORE)
        enforcer.set_mode("coder", AgentMode.EXPLORE)

        enforcer.can_execute("planner", "write_file")
        enforcer.can_execute("coder", "write_file")

        count = enforcer.get_violation_count(agent_name="planner")
        assert count == 1

    def test_clear_violations_all(self):
        """Test clearing all violations"""
        enforcer = ModeEnforcer()
        enforcer.set_mode("planner", AgentMode.EXPLORE)

        enforcer.can_execute("planner", "write_file")
        assert len(enforcer.violations) == 1

        enforcer.clear_violations()
        assert len(enforcer.violations) == 0

    def test_clear_violations_by_agent(self):
        """Test clearing violations for specific agent"""
        enforcer = ModeEnforcer()
        enforcer.set_mode("planner", AgentMode.EXPLORE)
        enforcer.set_mode("coder", AgentMode.EXPLORE)

        enforcer.can_execute("planner", "write_file")
        enforcer.can_execute("coder", "write_file")
        assert len(enforcer.violations) == 2

        enforcer.clear_violations(agent_name="planner")
        assert len(enforcer.violations) == 1
        assert enforcer.violations[0].agent_name == "coder"

    def test_is_write_action_write_keywords(self):
        """Test detecting write actions"""
        enforcer = ModeEnforcer()

        assert enforcer._is_write_action("write_file") is True
        assert enforcer._is_write_action("update_database") is True
        assert enforcer._is_write_action("delete_record") is True
        assert enforcer._is_write_action("create_table") is True

    def test_is_write_action_read_keywords(self):
        """Test detecting read actions"""
        enforcer = ModeEnforcer()

        assert enforcer._is_write_action("read_file") is False
        assert enforcer._is_write_action("search_database") is False
        assert enforcer._is_write_action("get_record") is False
        assert enforcer._is_write_action("fetch_data") is False

    def test_is_write_action_with_tool_name(self):
        """Test action detection with tool name"""
        enforcer = ModeEnforcer()

        assert enforcer._is_write_action("process", "write_tool") is True
        assert enforcer._is_write_action("process", "read_tool") is False

    def test_has_approval_no_callback(self):
        """Test approval check without callback"""
        enforcer = ModeEnforcer()
        assert enforcer._has_approval("planner") is False

    def test_has_approval_with_callback_true(self):
        """Test approval check with callback returning True"""
        enforcer = ModeEnforcer()
        enforcer.approval_callbacks["planner"] = lambda: True
        assert enforcer._has_approval("planner") is True

    def test_has_approval_with_callback_false(self):
        """Test approval check with callback returning False"""
        enforcer = ModeEnforcer()
        enforcer.approval_callbacks["planner"] = lambda: False
        assert enforcer._has_approval("planner") is False

    def test_has_approval_callback_exception(self):
        """Test approval check with callback exception"""
        enforcer = ModeEnforcer()

        def broken_callback():
            raise Exception("Callback failed")

        enforcer.approval_callbacks["planner"] = broken_callback
        assert enforcer._has_approval("planner") is False

    def test_record_violation(self):
        """Test recording violation"""
        enforcer = ModeEnforcer()

        enforcer._record_violation(
            agent_name="planner",
            declared_mode=AgentMode.EXPLORE,
            attempted_action="write_file",
            violation_type="write_in_explore",
            details="Test violation"
        )

        assert len(enforcer.violations) == 1
        violation = enforcer.violations[0]
        assert violation.agent_name == "planner"
        assert violation.violation_type == "write_in_explore"

    def test_multiple_agents_different_modes(self):
        """Test multiple agents with different modes"""
        enforcer = ModeEnforcer()

        enforcer.set_mode("planner", AgentMode.EXPLORE)
        enforcer.set_mode("coder", AgentMode.EXECUTE)
        enforcer.set_mode("reviewer", AgentMode.ESCALATE)

        assert enforcer.can_execute("planner", "read_file") is True
        assert enforcer.can_execute("planner", "write_file") is False
        assert enforcer.can_execute("coder", "write_file") is True
        assert enforcer.can_execute("reviewer", "write_file") is False

    def test_mode_switch(self):
        """Test switching agent mode"""
        enforcer = ModeEnforcer()

        enforcer.set_mode("planner", AgentMode.EXPLORE)
        assert enforcer.can_execute("planner", "write_file") is False

        enforcer.set_mode("planner", AgentMode.EXECUTE)
        assert enforcer.can_execute("planner", "write_file") is True
