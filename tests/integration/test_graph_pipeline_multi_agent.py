"""
Integration tests for GraphPipelineRunner multi-agent orchestration.

Tests that verify agent coordination, state sharing, conditional routing,
and parallel execution capabilities for agentic workflows.
"""

import pytest
from ia_modules.pipeline.graph_pipeline_runner import (
    GraphPipelineRunner,
    AgentStepWrapper
)
from ia_modules.pipeline.services import ServiceRegistry
from ia_modules.agents.state import StateManager
from typing import Dict, Any


class MockAgent:
    """Mock agent for testing agent-pipeline integration"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = config.get("agent_name", "unknown")
        self.state = StateManager(thread_id="test-thread")

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process data and return result in agent format"""
        # Simulate agent processing
        result_data = {
            **data,
            f"{self.name}_processed": True,
            "agent_name": self.name
        }

        return {
            "success": True,
            "data": result_data,
            "metadata": {"agent": self.name}
        }


class PlannerAgent:
    """Mock planner agent that creates a plan"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = "planner"

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data.get("task", "")
        plan = {
            "steps": ["research", "implement", "test"],
            "estimated_time": "2 hours",
            "complexity": "medium"
        }

        return {
            "success": True,
            "data": {**data, "plan": plan, "planner_complete": True}
        }


class ResearcherAgent:
    """Mock researcher agent that gathers information"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = "researcher"

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data.get("plan", {})
        research = {
            "findings": ["Finding 1", "Finding 2", "Finding 3"],
            "sources": ["source1.com", "source2.com"],
            "confidence": 0.85
        }

        return {
            "success": True,
            "data": {**data, "research": research, "researcher_complete": True}
        }


class CoderAgent:
    """Mock coder agent that generates code"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = "coder"

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        data.get("plan", {})
        data.get("research", {})

        code = {
            "implementation": "def solution(): pass",
            "tests": "def test_solution(): assert True",
            "quality_score": 0.9
        }

        return {
            "success": True,
            "data": {**data, "code": code, "coder_complete": True}
        }


class CriticAgent:
    """Mock critic agent that reviews work"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = "critic"
        self.approval_threshold = config.get("approval_threshold", 0.8)

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        code = data.get("code", {})
        quality_score = code.get("quality_score", 0.0)

        approved = quality_score >= self.approval_threshold

        review = {
            "approved": approved,
            "quality_score": quality_score,
            "feedback": "Looks good" if approved else "Needs improvement"
        }

        return {
            "success": True,
            "data": {**data, "review": review, "critic_complete": True}
        }


class DecisionAgent:
    """Mock decision agent that makes routing decisions"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.name = "decision"

    async def process(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # Make decision based on data
        complexity = data.get("plan", {}).get("complexity", "low")
        needs_research = complexity in ["medium", "high"]

        return {
            "success": True,
            "data": {
                **data,
                "needs_research": needs_research,
                "decision_complete": True
            }
        }


@pytest.mark.asyncio
class TestGraphPipelineMultiAgent:
    """Test multi-agent orchestration through GraphPipelineRunner."""

    async def test_sequential_agent_execution(self):
        """Agents execute sequentially and share state."""
        services = ServiceRegistry()
        GraphPipelineRunner(services)

        # Create pipeline with sequential agent steps

        # Create real agent instances and test with wrapper
        planner = PlannerAgent({})
        researcher = ResearcherAgent({})
        coder = CoderAgent({})

        # Simulate agent execution through wrappers
        input_data = {"task": "Build API"}

        # Step 1: Planner
        planner_result = await planner.process(input_data)
        assert planner_result["success"] is True
        data_after_planner = planner_result["data"]

        # Step 2: Researcher (receives planner output)
        researcher_result = await researcher.process(data_after_planner)
        assert researcher_result["success"] is True
        data_after_researcher = researcher_result["data"]

        # Step 3: Coder (receives researcher output)
        coder_result = await coder.process(data_after_researcher)
        assert coder_result["success"] is True
        final_data = coder_result["data"]

        # Verify state was shared across agents
        assert "plan" in final_data
        assert "research" in final_data
        assert "code" in final_data
        assert final_data["planner_complete"] is True
        assert final_data["researcher_complete"] is True
        assert final_data["coder_complete"] is True

    async def test_agent_wrapper_compatibility(self):
        """AgentStepWrapper correctly wraps agents for Step interface."""
        agent = PlannerAgent({"agent_name": "test_planner"})
        wrapper = AgentStepWrapper("planner_step", agent, {})

        input_data = {"task": "Test task"}
        result = await wrapper.run(input_data)

        # Wrapper should extract data from agent's success response
        assert "plan" in result
        assert result["planner_complete"] is True

    async def test_agent_wrapper_handles_failure(self):
        """AgentStepWrapper raises exception on agent failure."""

        class FailingAgent:
            async def process(self, data):
                return {"success": False, "error": "Agent failed"}

        agent = FailingAgent()
        wrapper = AgentStepWrapper("failing_step", agent, {})

        with pytest.raises(Exception, match="Agent failing_step failed"):
            await wrapper.run({"test": "data"})

    async def test_conditional_agent_routing(self):
        """Agents route conditionally based on data."""
        # Create decision agent that determines next step
        decision_agent = DecisionAgent({})
        planner_agent = PlannerAgent({})

        # Low complexity task
        low_complexity_data = {"task": "Simple task"}
        planner_result = await planner_agent.process(low_complexity_data)
        planner_data = planner_result["data"]
        planner_data["plan"]["complexity"] = "low"

        decision_result = await decision_agent.process(planner_data)
        decision_data = decision_result["data"]

        # Should not need research for low complexity
        assert decision_data["needs_research"] is False

        # High complexity task
        high_complexity_data = {"task": "Complex task"}
        planner_result = await planner_agent.process(high_complexity_data)
        planner_data = planner_result["data"]
        planner_data["plan"]["complexity"] = "high"

        decision_result = await decision_agent.process(planner_data)
        decision_data = decision_result["data"]

        # Should need research for high complexity
        assert decision_data["needs_research"] is True

    async def test_agent_feedback_loop(self):
        """Agents can implement feedback loops (coder -> critic -> coder)."""
        coder = CoderAgent({})
        critic = CriticAgent({"approval_threshold": 0.95})

        # First iteration - low quality
        data = {"task": "Build API", "plan": {}}
        coder_result = await coder.process(data)
        coder_data = coder_result["data"]
        coder_data["code"]["quality_score"] = 0.7  # Below threshold

        critic_result = await critic.process(coder_data)
        critic_data = critic_result["data"]

        # Should not be approved
        assert critic_data["review"]["approved"] is False
        assert "Needs improvement" in critic_data["review"]["feedback"]

        # Second iteration - improve quality
        coder_data["code"]["quality_score"] = 0.98  # Above threshold
        critic_result = await critic.process(coder_data)
        critic_data = critic_result["data"]

        # Should be approved
        assert critic_data["review"]["approved"] is True
        assert "Looks good" in critic_data["review"]["feedback"]

    async def test_agent_state_sharing(self):
        """Multiple agents share state correctly."""
        ServiceRegistry()

        # Create agents with shared state
        planner = PlannerAgent({})
        researcher = ResearcherAgent({})
        coder = CoderAgent({})

        # Execute pipeline manually to verify state sharing
        data = {"task": "Complex API"}

        # Planner creates plan
        result1 = await planner.process(data)
        data = result1["data"]
        assert "plan" in data

        # Researcher uses plan
        result2 = await researcher.process(data)
        data = result2["data"]
        assert "plan" in data  # Still has plan
        assert "research" in data  # Added research

        # Coder uses both plan and research
        result3 = await coder.process(data)
        data = result3["data"]
        assert "plan" in data
        assert "research" in data
        assert "code" in data

    async def test_parallel_agent_execution_simulation(self):
        """Simulate parallel agent execution."""
        import asyncio

        # Create multiple independent agents
        agents = [
            MockAgent({"agent_name": f"agent_{i}"})
            for i in range(3)
        ]

        input_data = {"task": "Test parallel"}

        # Execute agents in parallel
        tasks = [agent.process(input_data) for agent in agents]
        results = await asyncio.gather(*tasks)

        # All agents should complete successfully
        assert len(results) == 3
        for i, result in enumerate(results):
            assert result["success"] is True
            assert result["data"][f"agent_{i}_processed"] is True

    async def test_agent_error_propagation(self):
        """Errors in agents propagate correctly through pipeline."""

        class ErrorAgent:
            def __init__(self, config):
                self.config = config

            async def process(self, data):
                raise ValueError("Agent processing error")

        agent = ErrorAgent({})
        wrapper = AgentStepWrapper("error_agent", agent, {})

        with pytest.raises(ValueError, match="Agent processing error"):
            await wrapper.run({"test": "data"})

    async def test_multi_agent_pipeline_with_real_classes(self):
        """Test run_pipeline_with_real_classes method for agent pipeline."""
        services = ServiceRegistry()
        runner = GraphPipelineRunner(services)

        config_dict = {
            "name": "Real Agent Pipeline",
            "steps": [
                {
                    "id": "planner",
                    "name": "planner",
                    "step_class": "PlannerAgent",
                    "module": "test.agents"
                },
                {
                    "id": "coder",
                    "name": "coder",
                    "step_class": "CoderAgent",
                    "module": "test.agents"
                }
            ],
            "flow": {
                "start_at": "planner",
                "paths": [
                    {"from": "planner", "to": "coder", "condition": {"type": "always"}}
                ]
            }
        }

        # Provide real agent classes
        real_classes = {
            "PlannerAgent": PlannerAgent,
            "CoderAgent": CoderAgent
        }

        result = await runner.run_pipeline_with_real_classes(
            config_dict,
            {"task": "Build API"},
            real_classes
        )

        # Verify both agents executed
        # Result structure: {'input': {...}, 'steps': [...], 'output': {...}}
        output = result.get("output", result)  # Support both old and new structure
        assert "plan" in output
        assert "code" in output
        assert output["planner_complete"] is True
        assert output["coder_complete"] is True

    async def test_complex_multi_agent_workflow(self):
        """Test complex multi-agent workflow with branching and feedback."""
        # Create all agents
        planner = PlannerAgent({})
        decision = DecisionAgent({})
        researcher = ResearcherAgent({})
        coder = CoderAgent({})
        critic = CriticAgent({"approval_threshold": 0.85})

        # Simulate complex workflow
        data = {"task": "Build complex API"}

        # Step 1: Planner
        result = await planner.process(data)
        data = result["data"]
        data["plan"]["complexity"] = "high"

        # Step 2: Decision (should route to research)
        result = await decision.process(data)
        data = result["data"]
        assert data["needs_research"] is True

        # Step 3: Research (conditional)
        result = await researcher.process(data)
        data = result["data"]

        # Step 4: Coder
        result = await coder.process(data)
        data = result["data"]

        # Step 5: Critic
        result = await critic.process(data)
        data = result["data"]

        # Verify complete workflow
        assert "plan" in data
        assert "research" in data
        assert "code" in data
        assert "review" in data
        assert data["review"]["approved"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
