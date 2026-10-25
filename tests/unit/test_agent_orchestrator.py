"""
Unit tests for agent orchestrator.

Tests AgentOrchestrator with graph execution, feedback loops, and conditional branching.
"""
import pytest
from ia_modules.agents.core import AgentRole, BaseAgent
from ia_modules.agents.state import StateManager
from ia_modules.agents.orchestrator import AgentOrchestrator


# Test agents
class CounterAgent(BaseAgent):
    """Agent that increments a counter."""

    async def execute(self, input_data):
        count = await self.read_state("count", 0)
        await self.write_state("count", count + 1)
        return {"count": count + 1}


class SetValueAgent(BaseAgent):
    """Agent that sets a value."""

    async def execute(self, input_data):
        value = input_data.get("value", "default")
        await self.write_state(self.role.name, value)
        return {"value": value}


class CheckValueAgent(BaseAgent):
    """Agent that checks a value."""

    async def execute(self, input_data):
        check_key = input_data.get("check_key", "value")
        value = await self.read_state(check_key)
        result = value == "expected"
        await self.write_state("check_result", result)
        return {"result": result}


@pytest.mark.asyncio
class TestAgentOrchestrator:
    """Test AgentOrchestrator functionality."""

    async def test_orchestrator_creation(self):
        """Orchestrator can be created."""
        state = StateManager(thread_id="test-thread")
        orchestrator = AgentOrchestrator(state)

        assert orchestrator.state == state
        assert len(orchestrator.agents) == 0
        assert len(orchestrator.graph) == 0

    async def test_add_agent(self):
        """Agents can be added to orchestrator."""
        state = StateManager(thread_id="test-thread")
        orchestrator = AgentOrchestrator(state)

        role = AgentRole(name="counter", description="Counter agent")
        agent = CounterAgent(role, state)

        orchestrator.add_agent("agent1", agent)

        assert "agent1" in orchestrator.agents
        # Legacy BaseAgent is wrapped — verify underlying agent
        wrapper = orchestrator.agents["agent1"]
        assert wrapper.role.name == agent.role.name

    async def test_add_edge(self):
        """Edges can be added between agents."""
        state = StateManager(thread_id="test-thread")
        orchestrator = AgentOrchestrator(state)

        role1 = AgentRole(name="agent1", description="Agent 1")
        role2 = AgentRole(name="agent2", description="Agent 2")
        agent1 = CounterAgent(role1, state)
        agent2 = CounterAgent(role2, state)

        orchestrator.add_agent("agent1", agent1)
        orchestrator.add_agent("agent2", agent2)

        orchestrator.add_edge("agent1", "agent2")

        assert len(orchestrator.graph["agent1"]) == 1
        assert orchestrator.graph["agent1"][0].to == "agent2"

    async def test_simple_sequence(self):
        """Orchestrator executes simple sequence."""
        state = StateManager(thread_id="test-thread")
        orchestrator = AgentOrchestrator(state)

        # Create agents
        role1 = AgentRole(name="agent1", description="Agent 1")
        role2 = AgentRole(name="agent2", description="Agent 2")
        agent1 = CounterAgent(role1, state)
        agent2 = CounterAgent(role2, state)

        orchestrator.add_agent("agent1", agent1)
        orchestrator.add_agent("agent2", agent2)

        # Build sequence: agent1 → agent2
        orchestrator.add_edge("agent1", "agent2")

        # Run
        result = await orchestrator.run("agent1", {})

        # Both agents should have run
        assert await state.get("count") == 2
        assert result["count"] == 2

    async def test_conditional_branching(self):
        """Orchestrator handles conditional branching."""
        state = StateManager(thread_id="test-thread")
        orchestrator = AgentOrchestrator(state)

        # Create agents
        role1 = AgentRole(name="setter", description="Sets value")
        role2 = AgentRole(name="path_a", description="Path A")
        role3 = AgentRole(name="path_b", description="Path B")

        agent1 = SetValueAgent(role1, state)
        agent2 = SetValueAgent(role2, state)
        agent3 = SetValueAgent(role3, state)

        orchestrator.add_agent("setter", agent1)
        orchestrator.add_agent("path_a", agent2)
        orchestrator.add_agent("path_b", agent3)

        # Build conditional flow
        async def take_path_a(st):
            value = await st.get("setter")
            return value == "a"

        async def take_path_b(st):
            value = await st.get("setter")
            return value == "b"

        orchestrator.add_edge("setter", "path_a", condition=take_path_a)
        orchestrator.add_edge("setter", "path_b", condition=take_path_b)

        # Run with path A
        await orchestrator.run("setter", {"value": "a"})

        # path_a should have been executed with input value "a"
        assert await state.get("path_a") == "a"
        assert await state.get("path_b") is None

    async def test_feedback_loop(self):
        """Orchestrator handles feedback loops."""
        state = StateManager(thread_id="test-thread")
        orchestrator = AgentOrchestrator(state)

        # Create worker and critic
        worker_role = AgentRole(name="worker", description="Worker")
        critic_role = AgentRole(name="critic", description="Critic")

        worker = CounterAgent(worker_role, state)
        critic = CheckValueAgent(critic_role, state)

        orchestrator.add_agent("worker", worker)
        orchestrator.add_agent("critic", critic)

        # Add feedback loop
        orchestrator.add_feedback_loop("worker", "critic", max_iterations=3)

        # Set up state so critic never approves
        await state.set("approved", False)

        # Run
        await orchestrator.run("worker", {})

        # Should iterate 3 times
        iterations = await state.get("worker_iterations")
        assert iterations == 3

    async def test_feedback_loop_with_approval(self):
        """Feedback loop exits when approved."""
        state = StateManager(thread_id="test-thread")
        orchestrator = AgentOrchestrator(state)

        # Create agents
        worker_role = AgentRole(name="worker", description="Worker")
        critic_role = AgentRole(name="critic", description="Critic")

        class ApprovingCritic(BaseAgent):
            async def execute(self, input_data):
                # Approve on second iteration
                iterations = await self.read_state("worker_iterations", 0)
                approved = iterations >= 2
                await self.write_state("approved", approved)
                return {"approved": approved}

        worker = CounterAgent(worker_role, state)
        critic = ApprovingCritic(critic_role, state)

        orchestrator.add_agent("worker", worker)
        orchestrator.add_agent("critic", critic)

        # Add feedback loop
        orchestrator.add_feedback_loop("worker", "critic", max_iterations=5)

        # Run
        await orchestrator.run("worker", {})

        # Should iterate only 2 times (then approved)
        iterations = await state.get("worker_iterations")
        assert iterations == 2

    async def test_max_steps_prevention(self):
        """Orchestrator prevents infinite loops with max_steps."""
        state = StateManager(thread_id="test-thread")
        orchestrator = AgentOrchestrator(state)

        # Create agent that loops forever
        role1 = AgentRole(name="agent1", description="Agent 1")
        role2 = AgentRole(name="agent2", description="Agent 2")

        agent1 = CounterAgent(role1, state)
        agent2 = CounterAgent(role2, state)

        orchestrator.add_agent("agent1", agent1)
        orchestrator.add_agent("agent2", agent2)

        # Build infinite loop: agent1 → agent2 → agent1
        orchestrator.add_edge("agent1", "agent2")
        orchestrator.add_edge("agent2", "agent1")

        # Run with low max_steps
        with pytest.raises(RuntimeError, match="Max steps"):
            await orchestrator.run("agent1", {}, max_steps=5)

    async def test_execution_path_tracking(self):
        """Orchestrator tracks execution path."""
        state = StateManager(thread_id="test-thread")
        orchestrator = AgentOrchestrator(state)

        # Create 3 agents in sequence
        for i in range(1, 4):
            role = AgentRole(name=f"agent{i}", description=f"Agent {i}")
            agent = CounterAgent(role, state)
            orchestrator.add_agent(f"agent{i}", agent)

        orchestrator.add_edge("agent1", "agent2")
        orchestrator.add_edge("agent2", "agent3")

        # Run
        await orchestrator.run("agent1", {})

        # Check execution path
        path = await state.get("execution_path")
        assert path == ["agent1", "agent2", "agent3"]

        steps = await state.get("total_steps")
        assert steps == 3

    async def test_agent_stats(self):
        """Orchestrator provides statistics."""
        state = StateManager(thread_id="test-thread")
        orchestrator = AgentOrchestrator(state)

        # Add agents and edges
        for i in range(1, 4):
            role = AgentRole(name=f"agent{i}", description=f"Agent {i}")
            agent = CounterAgent(role, state)
            orchestrator.add_agent(f"agent{i}", agent)

        orchestrator.add_edge("agent1", "agent2")
        orchestrator.add_edge("agent2", "agent3")

        stats = orchestrator.get_agent_stats()

        assert stats["num_agents"] == 3
        assert stats["num_edges"] == 2
        assert "agent1" in stats["agents"]
        assert "agent2" in stats["agents"]
        assert "agent3" in stats["agents"]

    async def test_visualize(self):
        """Orchestrator can generate Mermaid diagram."""
        state = StateManager(thread_id="test-thread")
        orchestrator = AgentOrchestrator(state)

        # Add agents
        role1 = AgentRole(name="planner", description="Planner")
        role2 = AgentRole(name="coder", description="Coder")

        agent1 = CounterAgent(role1, state)
        agent2 = CounterAgent(role2, state)

        orchestrator.add_agent("planner", agent1)
        orchestrator.add_agent("coder", agent2)

        orchestrator.add_edge("planner", "coder")

        # Visualize
        diagram = orchestrator.visualize()

        assert "graph TD" in diagram
        assert "planner" in diagram
        assert "coder" in diagram

    async def test_unknown_start_agent(self):
        """Orchestrator raises error for unknown start agent."""
        state = StateManager(thread_id="test-thread")
        orchestrator = AgentOrchestrator(state)

        with pytest.raises(ValueError, match="Unknown start step"):
            await orchestrator.run("nonexistent", {})

    async def test_orchestrator_repr(self):
        """Orchestrator has useful repr."""
        state = StateManager(thread_id="test-thread")
        orchestrator = AgentOrchestrator(state)

        # Add agents
        role = AgentRole(name="agent1", description="Agent 1")
        agent = CounterAgent(role, state)
        orchestrator.add_agent("agent1", agent)

        repr_str = repr(orchestrator)
        assert "AgentOrchestrator" in repr_str
        assert "steps=1" in repr_str
