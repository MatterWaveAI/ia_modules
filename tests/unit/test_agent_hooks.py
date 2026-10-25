"""
Test Agent Execution Hooks

Verifies that AgentOrchestrator hooks work correctly for monitoring
agent lifecycle events.
"""

import pytest
from ia_modules.agents.orchestrator import AgentOrchestrator
from ia_modules.agents.core import BaseAgent
from ia_modules.agents.core import AgentRole
from ia_modules.agents.state import StateManager


class DemoAgent(BaseAgent):
    """Simple demo agent for testing"""
    
    async def execute(self, data: dict) -> dict:
        """Execute test logic"""
        return {**data, "processed": True}


@pytest.mark.asyncio
class TestAgentHooks:
    """Test execution hooks functionality"""
    
    async def test_agent_start_hook(self):
        """Agent start hook is invoked"""
        state = StateManager(thread_id="test")
        orchestrator = AgentOrchestrator(state)
        
        role = AgentRole(name="test_agent", description="Test")
        agent = DemoAgent(role, state)
        orchestrator.add_agent("agent1", agent)
        
        # Track hook calls
        hook_calls = []
        
        async def on_start(agent_id: str, input_data: dict):
            hook_calls.append({"event": "start", "agent": agent_id, "data": input_data})
        
        orchestrator.add_hook("agent_start", on_start)
        
        # Execute
        await orchestrator.run("agent1", {"input": "test"})
        
        # Verify hook was called
        assert len(hook_calls) == 1
        assert hook_calls[0]["event"] == "start"
        assert hook_calls[0]["agent"] == "agent1"
        assert hook_calls[0]["data"] == {"input": "test"}
    
    async def test_agent_complete_hook(self):
        """Agent complete hook is invoked with duration"""
        state = StateManager(thread_id="test")
        orchestrator = AgentOrchestrator(state)
        
        role = AgentRole(name="test_agent", description="Test")
        agent = DemoAgent(role, state)
        orchestrator.add_agent("agent1", agent)
        
        # Track hook calls
        hook_calls = []
        
        async def on_complete(agent_id: str, output_data: dict, duration: float):
            hook_calls.append({
                "event": "complete",
                "agent": agent_id,
                "output": output_data,
                "duration": duration
            })
        
        orchestrator.add_hook("agent_complete", on_complete)
        
        # Execute
        await orchestrator.run("agent1", {"input": "test"})
        
        # Verify hook was called
        assert len(hook_calls) == 1
        assert hook_calls[0]["event"] == "complete"
        assert hook_calls[0]["agent"] == "agent1"
        assert hook_calls[0]["output"]["processed"] is True
        assert hook_calls[0]["duration"] >= 0  # Duration should be measured
    
    async def test_agent_error_hook(self):
        """Agent error hook is invoked on failure"""
        state = StateManager(thread_id="test")
        orchestrator = AgentOrchestrator(state)
        
        # Create failing agent
        class FailingAgent(BaseAgent):
            async def execute(self, data: dict) -> dict:
                raise ValueError("Test error")
        
        role = AgentRole(name="failing", description="Test")
        agent = FailingAgent(role, state)
        orchestrator.add_agent("agent1", agent)
        
        # Track hook calls
        hook_calls = []
        
        async def on_error(agent_id: str, error: Exception):
            hook_calls.append({
                "event": "error",
                "agent": agent_id,
                "error": str(error)
            })
        
        orchestrator.add_hook("agent_error", on_error)
        
        # Execute (should fail)
        with pytest.raises(ValueError, match="Test error"):
            await orchestrator.run("agent1", {"input": "test"})
        
        # Verify error hook was called
        assert len(hook_calls) == 1
        assert hook_calls[0]["event"] == "error"
        assert hook_calls[0]["agent"] == "agent1"
        assert "Test error" in hook_calls[0]["error"]
    
    async def test_multiple_hooks(self):
        """Multiple hooks can be registered for same event"""
        state = StateManager(thread_id="test")
        orchestrator = AgentOrchestrator(state)
        
        role = AgentRole(name="test_agent", description="Test")
        agent = DemoAgent(role, state)
        orchestrator.add_agent("agent1", agent)
        
        # Track calls from multiple hooks
        calls1 = []
        calls2 = []
        
        async def hook1(agent_id: str, input_data: dict):
            calls1.append(agent_id)
        
        async def hook2(agent_id: str, input_data: dict):
            calls2.append(agent_id)
        
        orchestrator.add_hook("agent_start", hook1)
        orchestrator.add_hook("agent_start", hook2)
        
        # Execute
        await orchestrator.run("agent1", {"input": "test"})
        
        # Both hooks should be called
        assert len(calls1) == 1
        assert len(calls2) == 1
    
    async def test_hook_failure_doesnt_break_workflow(self):
        """Hook failure doesn't prevent workflow execution"""
        state = StateManager(thread_id="test")
        orchestrator = AgentOrchestrator(state)
        
        role = AgentRole(name="test_agent", description="Test")
        agent = DemoAgent(role, state)
        orchestrator.add_agent("agent1", agent)
        
        # Create failing hook
        async def failing_hook(agent_id: str, input_data: dict):
            raise RuntimeError("Hook failed")
        
        orchestrator.add_hook("agent_start", failing_hook)
        
        # Execute - should succeed despite hook failure
        result = await orchestrator.run("agent1", {"input": "test"})
        
        # Workflow should complete successfully (check execution_path in state)
        assert "execution_path" in result
        assert result["execution_path"] == ["agent1"]
    
    async def test_sequential_agents_with_hooks(self):
        """Hooks track sequential agent execution"""
        state = StateManager(thread_id="test")
        orchestrator = AgentOrchestrator(state)
        
        # Create two agents
        role1 = AgentRole(name="agent1", description="First")
        role2 = AgentRole(name="agent2", description="Second")
        agent1 = DemoAgent(role1, state)
        agent2 = DemoAgent(role2, state)
        
        orchestrator.add_agent("agent1", agent1)
        orchestrator.add_agent("agent2", agent2)
        orchestrator.add_edge("agent1", "agent2")
        
        # Track execution order
        execution_order = []
        
        async def on_start(agent_id: str, input_data: dict):
            execution_order.append(agent_id)
        
        orchestrator.add_hook("agent_start", on_start)
        
        # Execute
        await orchestrator.run("agent1", {"input": "test"})
        
        # Verify both agents executed in order
        assert execution_order == ["agent1", "agent2"]
    
    async def test_invalid_hook_event(self):
        """Invalid hook event raises error"""
        state = StateManager(thread_id="test")
        orchestrator = AgentOrchestrator(state)
        
        async def dummy_hook(agent_id: str):
            pass
        
        # Should raise error for invalid event
        with pytest.raises(ValueError, match="Unknown hook event"):
            orchestrator.add_hook("invalid_event", dummy_hook)
