"""
Unit tests for agent core functionality.

Tests AgentRole and BaseAgent.
"""
import pytest
from ia_modules.agents.core import AgentRole, BaseAgent
from ia_modules.agents.state import StateManager


class DummyAgent(BaseAgent):
    """Dummy agent for testing."""

    async def execute(self, input_data):
        # Read from state
        value = await self.read_state("test_key", "default")

        # Write to state
        await self.write_state("result", f"processed:{value}")

        return {"status": "success", "value": value}


class TestAgentRole:
    """Test AgentRole dataclass."""

    def test_agent_role_creation_minimal(self):
        """AgentRole can be created with minimal fields."""
        role = AgentRole(
            name="test_agent",
            description="Test agent for testing"
        )

        assert role.name == "test_agent"
        assert role.description == "Test agent for testing"
        assert role.allowed_tools == []
        assert role.system_prompt == ""
        assert role.max_iterations == 10
        assert role.metadata == {}

    def test_agent_role_creation_full(self):
        """AgentRole can be created with all fields."""
        role = AgentRole(
            name="researcher",
            description="Research agent",
            allowed_tools=["web_search", "calculator"],
            system_prompt="You are a research agent...",
            max_iterations=5,
            metadata={"temperature": 0.7}
        )

        assert role.name == "researcher"
        assert role.allowed_tools == ["web_search", "calculator"]
        assert role.system_prompt == "You are a research agent..."
        assert role.max_iterations == 5
        assert role.metadata == {"temperature": 0.7}


@pytest.mark.asyncio
class TestBaseAgent:
    """Test BaseAgent functionality."""

    async def test_agent_creation(self):
        """Agent can be created with role and state."""
        role = AgentRole(name="test", description="Test agent")
        state = StateManager(thread_id="test-thread")

        agent = DummyAgent(role, state)

        assert agent.role == role
        assert agent.state == state
        assert agent.iteration_count == 0

    async def test_agent_execute(self):
        """Agent can execute its task."""
        role = AgentRole(name="test", description="Test agent")
        state = StateManager(thread_id="test-thread")
        agent = DummyAgent(role, state)

        # Set up state
        await state.set("test_key", "test_value")

        # Execute agent
        result = await agent.execute({})

        assert result["status"] == "success"
        assert result["value"] == "test_value"

        # Check state was updated
        result_value = await state.get("result")
        assert result_value == "processed:test_value"

    async def test_read_state(self):
        """Agent can read from state."""
        role = AgentRole(name="test", description="Test agent")
        state = StateManager(thread_id="test-thread")
        agent = DummyAgent(role, state)

        # Set state
        await state.set("key1", "value1")

        # Read via agent
        value = await agent.read_state("key1")
        assert value == "value1"

    async def test_read_state_with_default(self):
        """Agent read_state returns default for missing keys."""
        role = AgentRole(name="test", description="Test agent")
        state = StateManager(thread_id="test-thread")
        agent = DummyAgent(role, state)

        # Read missing key
        value = await agent.read_state("missing_key", "default_value")
        assert value == "default_value"

    async def test_write_state(self):
        """Agent can write to state."""
        role = AgentRole(name="test", description="Test agent")
        state = StateManager(thread_id="test-thread")
        agent = DummyAgent(role, state)

        # Write via agent
        await agent.write_state("new_key", "new_value")

        # Verify in state
        value = await state.get("new_key")
        assert value == "new_value"

    async def test_get_state_snapshot(self):
        """Agent can get state snapshot."""
        role = AgentRole(name="test", description="Test agent")
        state = StateManager(thread_id="test-thread")
        agent = DummyAgent(role, state)

        # Set some state
        await state.set("key1", "value1")
        await state.set("key2", "value2")

        # Get snapshot
        snapshot = await agent.get_state_snapshot()

        assert snapshot == {"key1": "value1", "key2": "value2"}

    async def test_iteration_tracking(self):
        """Agent tracks iterations correctly."""
        role = AgentRole(name="test", description="Test agent")
        state = StateManager(thread_id="test-thread")
        agent = DummyAgent(role, state)

        assert agent.iteration_count == 0

        # Increment
        count1 = agent.increment_iteration()
        assert count1 == 1
        assert agent.iteration_count == 1

        count2 = agent.increment_iteration()
        assert count2 == 2
        assert agent.iteration_count == 2

    async def test_reset_iterations(self):
        """Agent can reset iteration counter."""
        role = AgentRole(name="test", description="Test agent")
        state = StateManager(thread_id="test-thread")
        agent = DummyAgent(role, state)

        # Increment
        agent.increment_iteration()
        agent.increment_iteration()
        assert agent.iteration_count == 2

        # Reset
        agent.reset_iterations()
        assert agent.iteration_count == 0

    async def test_agent_repr(self):
        """Agent has useful repr."""
        role = AgentRole(name="test", description="Test agent")
        state = StateManager(thread_id="test-thread")
        agent = DummyAgent(role, state)

        repr_str = repr(agent)
        assert "DummyAgent" in repr_str
        assert "test" in repr_str
