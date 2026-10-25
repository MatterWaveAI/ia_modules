"""
Comprehensive unit tests for AgentOrchestrator

Tests all methods and edge cases in agents/orchestrator.py to achieve 100% coverage
"""

import pytest
from unittest.mock import AsyncMock

from ia_modules.agents.orchestrator import AgentOrchestrator, Edge
from ia_modules.agents.state import StateManager
from ia_modules.agents.core import BaseAgent, AgentRole


class MockAgent(BaseAgent):
    """Mock agent for testing"""

    def __init__(self, role: AgentRole, state_manager: StateManager, behavior: callable = None):
        super().__init__(role, state_manager)
        self.behavior = behavior or self._default_behavior
        self.execute_mock = AsyncMock(side_effect=self.behavior)

    async def _default_behavior(self, input_data):
        return {"status": "success"}

    async def execute(self, input_data):
        """Concrete implementation of abstract method"""
        result = await self.execute_mock(input_data)
        return result


class TestEdge:
    """Test Edge dataclass"""

    def test_edge_minimal(self):
        """Test creating edge with minimal parameters"""
        edge = Edge(to="target")

        assert edge.to == "target"
        assert edge.condition is None
        assert edge.metadata == {}

    def test_edge_with_condition(self):
        """Test edge with condition function"""
        async def cond(state):
            return True

        edge = Edge(to="target", condition=cond)

        assert edge.condition == cond

    def test_edge_with_metadata(self):
        """Test edge with metadata"""
        edge = Edge(to="target", metadata={"type": "feedback"})

        assert edge.metadata == {"type": "feedback"}

    def test_edge_post_init_creates_metadata(self):
        """Test that post_init creates empty metadata dict"""
        edge = Edge(to="target")

        # Should not be None, should be empty dict
        assert edge.metadata is not None
        assert isinstance(edge.metadata, dict)


class TestOrchestratorInit:
    """Test AgentOrchestrator initialization"""

    def test_init(self):
        """Test orchestrator initialization"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        assert orch.state == state
        assert orch.agents == {}
        assert orch.graph == {}
        assert orch.logger is not None
        assert orch.on_agent_start == []
        assert orch.on_agent_complete == []
        assert orch.on_agent_error == []


class TestOrchestratorAddAgent:
    """Test adding agents"""

    def test_add_agent(self):
        """Test adding single agent"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        role = AgentRole(name="planner", description="Plans tasks")
        agent = MockAgent(role, state)

        orch.add_agent("planner", agent)

        assert "planner" in orch.steps
        assert type(orch.steps["planner"]).__name__ == "_LegacyAgentWrapper"
        assert "planner" in orch.graph
        assert orch.graph["planner"] == []

    def test_add_multiple_agents(self):
        """Test adding multiple agents"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        role1 = AgentRole(name="planner", description="Plans")
        role2 = AgentRole(name="coder", description="Codes")
        agent1 = MockAgent(role1, state)
        agent2 = MockAgent(role2, state)

        orch.add_agent("planner", agent1)
        orch.add_agent("coder", agent2)

        assert len(orch.agents) == 2


class TestOrchestratorHooks:
    """Test lifecycle hooks"""

    def test_add_hook_agent_start(self):
        """Test adding agent_start hook"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        async def hook(agent_id, input_data):
            pass

        orch.add_hook("agent_start", hook)

        assert hook in orch.on_agent_start

    def test_add_hook_agent_complete(self):
        """Test adding agent_complete hook"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        async def hook(agent_id, output_data, duration):
            pass

        orch.add_hook("agent_complete", hook)

        assert hook in orch.on_agent_complete

    def test_add_hook_agent_error(self):
        """Test adding agent_error hook"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        async def hook(agent_id, error):
            pass

        orch.add_hook("agent_error", hook)

        assert hook in orch.on_agent_error

    def test_add_hook_invalid_event(self):
        """Test adding hook with invalid event type"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        async def hook():
            pass

        with pytest.raises(ValueError, match="Unknown hook event"):
            orch.add_hook("invalid_event", hook)

    def test_add_multiple_hooks(self):
        """Test adding multiple hooks for same event"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        async def hook1(agent_id, input_data):
            pass

        async def hook2(agent_id, input_data):
            pass

        orch.add_hook("agent_start", hook1)
        orch.add_hook("agent_start", hook2)

        assert len(orch.on_agent_start) == 2


class TestOrchestratorEdges:
    """Test adding edges"""

    def test_add_edge_unconditional(self):
        """Test adding unconditional edge"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        orch.add_edge("planner", "coder")

        assert len(orch.graph["planner"]) == 1
        assert orch.graph["planner"][0].to == "coder"
        assert orch.graph["planner"][0].condition is None

    def test_add_edge_with_condition(self):
        """Test adding conditional edge"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        async def cond(state):
            return True

        orch.add_edge("planner", "coder", condition=cond)

        assert orch.graph["planner"][0].condition == cond

    def test_add_edge_with_metadata(self):
        """Test adding edge with metadata"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        orch.add_edge("planner", "coder", metadata={"type": "main"})

        assert orch.graph["planner"][0].metadata == {"type": "main"}

    def test_add_multiple_edges_from_same_node(self):
        """Test adding multiple edges from same node"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        orch.add_edge("planner", "coder")
        orch.add_edge("planner", "reviewer")

        assert len(orch.graph["planner"]) == 2


class TestOrchestratorFeedbackLoop:
    """Test feedback loop creation"""

    @pytest.mark.asyncio
    async def test_add_feedback_loop(self):
        """Test adding feedback loop"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        is_complete = orch.add_feedback_loop("coder", "critic", max_iterations=3)

        # Should create 2 edges
        assert len(orch.graph["coder"]) == 1  # coder → critic
        assert len(orch.graph["critic"]) == 1  # critic → coder (conditional)
        assert callable(is_complete)

    @pytest.mark.asyncio
    async def test_feedback_loop_with_next_agent(self):
        """Test feedback loop with next agent"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        orch.add_feedback_loop("coder", "critic", max_iterations=3, next_step="formatter")

        # Should create 3 edges
        assert len(orch.graph["critic"]) == 2  # critic → coder (cond), critic → formatter (cond)

    @pytest.mark.asyncio
    async def test_feedback_loop_needs_revision_approved(self):
        """Test needs_revision returns False when approved"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        orch.add_feedback_loop("coder", "critic", max_iterations=3)

        # Set approved = True
        await state.set("approved", True)

        # Get the needs_revision condition
        needs_revision = orch.graph["critic"][0].condition

        result = await needs_revision(state)
        assert result is False

    @pytest.mark.asyncio
    async def test_feedback_loop_needs_revision_under_max(self):
        """Test needs_revision returns True when not approved and under max"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        orch.add_feedback_loop("coder", "critic", max_iterations=3)

        # Set approved = False, iterations = 0
        await state.set("approved", False)

        # Get the needs_revision condition
        needs_revision = orch.graph["critic"][0].condition

        result = await needs_revision(state)
        assert result is True

        # Should increment iteration count
        iterations = await state.get("coder_iterations")
        assert iterations == 1

    @pytest.mark.asyncio
    async def test_feedback_loop_is_complete_approved(self):
        """Test is_complete returns True when approved"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        is_complete = orch.add_feedback_loop("coder", "critic", max_iterations=3)

        await state.set("approved", True)

        result = await is_complete(state)
        assert result is True

    @pytest.mark.asyncio
    async def test_feedback_loop_is_complete_max_iterations(self):
        """Test is_complete returns True when max iterations reached"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        is_complete = orch.add_feedback_loop("coder", "critic", max_iterations=3)

        await state.set("approved", False)
        await state.set("coder_iterations", 3)

        result = await is_complete(state)
        assert result is True


class TestOrchestratorRun:
    """Test workflow execution"""

    @pytest.mark.asyncio
    async def test_run_single_agent(self):
        """Test running workflow with single agent"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        role = AgentRole(name="planner", description="Plans")
        agent = MockAgent(role, state)

        orch.add_agent("planner", agent)

        result = await orch.run("planner", {"task": "test"})

        agent.execute_mock.assert_called_once()
        assert "execution_path" in result
        assert result["execution_path"] == ["planner"]

    @pytest.mark.asyncio
    async def test_run_sequential_agents(self):
        """Test running sequential workflow"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        role1 = AgentRole(name="planner", description="Plans")
        role2 = AgentRole(name="coder", description="Codes")
        agent1 = MockAgent(role1, state)
        agent2 = MockAgent(role2, state)

        orch.add_agent("planner", agent1)
        orch.add_agent("coder", agent2)
        orch.add_edge("planner", "coder")

        result = await orch.run("planner", {"task": "test"})

        assert result["execution_path"] == ["planner", "coder"]
        assert result["total_steps"] == 2

    @pytest.mark.asyncio
    async def test_run_unknown_start_agent(self):
        """Test run with unknown start agent"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        with pytest.raises(ValueError, match="Unknown start step"):
            await orch.run("unknown", {})

    @pytest.mark.asyncio
    async def test_run_max_steps_exceeded(self):
        """Test run with max steps exceeded"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        role = AgentRole(name="agent", description="Test")
        agent = MockAgent(role, state)

        orch.add_agent("agent", agent)
        # Create self-loop
        orch.add_edge("agent", "agent")

        with pytest.raises(RuntimeError, match="Max steps.*exceeded"):
            await orch.run("agent", {}, max_steps=5)

    @pytest.mark.asyncio
    async def test_run_with_hooks(self):
        """Test run invokes hooks"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        role = AgentRole(name="planner", description="Plans")
        agent = MockAgent(role, state)

        orch.add_agent("planner", agent)

        start_hook = AsyncMock()
        complete_hook = AsyncMock()

        orch.add_hook("agent_start", start_hook)
        orch.add_hook("agent_complete", complete_hook)

        await orch.run("planner", {"task": "test"})

        start_hook.assert_called_once()
        complete_hook.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_hook_failures_handled(self):
        """Test that hook failures don't break execution"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        role = AgentRole(name="planner", description="Plans")
        agent = MockAgent(role, state)

        orch.add_agent("planner", agent)

        # Add hook that raises exception
        async def failing_hook(agent_id, input_data):
            raise Exception("Hook failed")

        orch.add_hook("agent_start", failing_hook)

        # Should not raise exception
        result = await orch.run("planner", {"task": "test"})

        assert "execution_path" in result

    @pytest.mark.asyncio
    async def test_run_agent_error_invokes_error_hooks(self):
        """Test agent error invokes error hooks"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        role = AgentRole(name="planner", description="Plans")

        # Create agent that fails
        async def failing_behavior(input_data):
            raise ValueError("Agent failed")

        agent = MockAgent(role, state, behavior=failing_behavior)

        orch.add_agent("planner", agent)

        error_hook = AsyncMock()
        orch.add_hook("agent_error", error_hook)

        with pytest.raises(ValueError):
            await orch.run("planner", {"task": "test"})

        error_hook.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_agent_error_sets_state(self):
        """Test agent error sets error state"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        role = AgentRole(name="planner", description="Plans")

        async def failing_behavior(input_data):
            raise ValueError("Agent failed")

        agent = MockAgent(role, state, behavior=failing_behavior)

        orch.add_agent("planner", agent)

        with pytest.raises(ValueError):
            await orch.run("planner", {"task": "test"})

        error = await state.get("error")
        failed_step = await state.get("failed_step")

        assert "Agent failed" in error
        assert failed_step == "planner"


class TestOrchestratorGetNextAgent:
    """Test next agent selection"""

    @pytest.mark.asyncio
    async def test_get_next_agent_unconditional(self):
        """Test getting next agent with unconditional edge"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        orch.add_edge("planner", "coder")

        next_agent = await orch._get_next_step("planner")

        assert next_agent == "coder"

    @pytest.mark.asyncio
    async def test_get_next_agent_no_edges(self):
        """Test getting next agent when no edges"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        next_agent = await orch._get_next_step("planner")

        assert next_agent is None

    @pytest.mark.asyncio
    async def test_get_next_agent_condition_true(self):
        """Test getting next agent when condition is True"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        async def cond(state):
            return True

        orch.add_edge("planner", "coder", condition=cond)

        next_agent = await orch._get_next_step("planner")

        assert next_agent == "coder"

    @pytest.mark.asyncio
    async def test_get_next_agent_condition_false(self):
        """Test getting next agent when condition is False"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        async def cond(state):
            return False

        orch.add_edge("planner", "coder", condition=cond)

        next_agent = await orch._get_next_step("planner")

        assert next_agent is None

    @pytest.mark.asyncio
    async def test_get_next_agent_first_matching_condition(self):
        """Test getting first agent with matching condition"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        async def cond1(state):
            return False

        async def cond2(state):
            return True

        orch.add_edge("planner", "coder", condition=cond1)
        orch.add_edge("planner", "reviewer", condition=cond2)

        next_agent = await orch._get_next_step("planner")

        # Should return second one since first condition is False
        assert next_agent == "reviewer"

    @pytest.mark.asyncio
    async def test_get_next_agent_condition_exception_handled(self):
        """Test condition exception is handled gracefully"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        async def failing_cond(state):
            raise Exception("Condition failed")

        async def working_cond(state):
            return True

        orch.add_edge("planner", "coder", condition=failing_cond)
        orch.add_edge("planner", "reviewer", condition=working_cond)

        # Should skip failing condition and try next
        next_agent = await orch._get_next_step("planner")

        assert next_agent == "reviewer"


class TestOrchestratorVisualize:
    """Test workflow visualization"""

    def test_visualize_simple_workflow(self):
        """Test visualizing simple workflow"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        role1 = AgentRole(name="Planner", description="Plans")
        role2 = AgentRole(name="Coder", description="Codes")
        agent1 = MockAgent(role1, state)
        agent2 = MockAgent(role2, state)

        orch.add_agent("planner", agent1)
        orch.add_agent("coder", agent2)
        orch.add_edge("planner", "coder")

        diagram = orch.visualize()

        assert "graph TD" in diagram
        assert "planner[Planner] --> coder[Coder]" in diagram

    def test_visualize_conditional_edge(self):
        """Test visualizing conditional edge"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        role1 = AgentRole(name="Planner", description="Plans")
        role2 = AgentRole(name="Coder", description="Codes")
        agent1 = MockAgent(role1, state)
        agent2 = MockAgent(role2, state)

        orch.add_agent("planner", agent1)
        orch.add_agent("coder", agent2)

        async def needs_code(state):
            return True

        orch.add_edge("planner", "coder", condition=needs_code)

        diagram = orch.visualize()

        assert "planner[Planner] -->|needs_code| coder[Coder]" in diagram

    def test_visualize_agent_not_in_agents(self):
        """Test visualizing when agent not in agents dict"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        # Add edge without adding agents
        orch.graph["unknown1"] = [Edge(to="unknown2")]

        diagram = orch.visualize()

        # Should use agent_id as label
        assert "unknown1" in diagram


class TestOrchestratorStats:
    """Test statistics"""

    @pytest.mark.asyncio
    async def test_get_agent_stats(self):
        """Test getting orchestrator stats"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        role1 = AgentRole(name="planner", description="Plans")
        role2 = AgentRole(name="coder", description="Codes")
        agent1 = MockAgent(role1, state)
        agent2 = MockAgent(role2, state)

        orch.add_agent("planner", agent1)
        orch.add_agent("coder", agent2)
        orch.add_edge("planner", "coder")

        await state.set("key1", "value1")

        stats = orch.get_agent_stats()

        assert stats["num_agents"] == 2
        assert stats["num_edges"] == 1
        assert "planner" in stats["agents"]
        assert "coder" in stats["agents"]
        assert stats["state_keys"] == 1
        assert stats["state_versions"] == 1

    def test_repr(self):
        """Test __repr__ method"""
        state = StateManager(thread_id="test")
        orch = AgentOrchestrator(state)

        role = AgentRole(name="planner", description="Plans")
        agent = MockAgent(role, state)

        orch.add_agent("planner", agent)
        orch.add_edge("planner", "coder")

        repr_str = repr(orch)

        assert "steps=1" in repr_str
        assert "edges=1" in repr_str


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
