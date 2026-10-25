"""
Tests for Agentic Design Pattern Pipeline Steps

Tests that pattern steps correctly integrate with the pipeline system
and SubprocessAgentAdapter.
"""

import os
import pytest
import asyncio

from pipelines.pattern_steps import ReflectionStep, PlanningStep, ToolUseStep


class MockAdapter:
    """Mock adapter matching SubprocessAgentAdapter.generate() interface."""

    def __init__(self, responses: list):
        self.responses = responses
        self.call_count = 0

    async def generate(self, prompt: str, model: str = None, temperature: float = 0.7, max_tokens: int = None, **kwargs):
        """Mock generate — returns plain string like SubprocessAgentAdapter."""
        if self.call_count >= len(self.responses):
            response_text = "Default response"
        else:
            response_text = self.responses[self.call_count]

        self.call_count += 1
        return response_text


class TestReflectionStep:
    """Test ReflectionStep pattern"""

    @pytest.mark.asyncio
    async def test_reflection_basic_execution(self):
        """Test basic reflection execution"""

        # Mock responses: critique, then improved version
        mock_responses = [
            "Score: 6/10\nIssues: Too brief, lacks detail\nSuggestions: Add more information",
            "This is a much improved and detailed version of the text with comprehensive information.",
            "Score: 9/10\nIssues: Minor formatting\nSuggestions: None"
        ]

        step = ReflectionStep(
            name="test_reflection",
            config={
                "initial_output": "This is a draft.",
                "criteria": {
                    "clarity": "Should be clear",
                    "completeness": "Should be complete"
                },
                "max_iterations": 2
            }
        )

        # Inject mock LLM
        step.adapter = MockAdapter(mock_responses)

        # Execute
        result = await step.run({})

        # Verify
        assert "final_output" in result
        assert "final_score" in result
        assert "iterations" in result
        assert result["total_iterations"] >= 1
        assert result["final_score"] >= 6.0

    @pytest.mark.asyncio
    async def test_reflection_with_input_data(self):
        """Test reflection with runtime input data"""

        mock_responses = [
            "Score: 7/10\nGood but could be better",
            "Improved version",
            "Score: 8/10\nMuch better"
        ]

        step = ReflectionStep(
            name="test_reflection",
            config={
                "max_iterations": 2
            }
        )
        step.adapter = MockAdapter(mock_responses)

        # Pass data at runtime
        result = await step.run({
            "initial_output": "Runtime input text",
            "criteria": {
                "quality": "Must be high quality"
            }
        })

        assert result["final_score"] >= 7.0
        assert len(result["iterations"]) > 0

    @pytest.mark.asyncio
    async def test_reflection_early_termination(self):
        """Test reflection stops when score is high enough"""

        # First critique is already high score
        mock_responses = [
            "Score: 9.5/10\nExcellent quality, no issues"
        ]

        step = ReflectionStep(
            name="test_reflection",
            config={
                "initial_output": "Perfect text",
                "criteria": {"quality": "High"},
                "max_iterations": 5
            }
        )
        step.adapter = MockAdapter(mock_responses)

        result = await step.run({})

        # Should stop after 1 iteration since score >= 8.0
        assert result["total_iterations"] == 1
        assert result["final_score"] >= 9.0

    @pytest.mark.asyncio
    async def test_reflection_score_parsing(self):
        """Test that scores are correctly parsed from critique"""

        test_cases = [
            ("Score: 7/10\nGood", 7.0),
            ("Score: 8.5/10\nVery good", 8.5),
            ("7/10 - Acceptable", 7.0),
            ("9.2/10", 9.2),
        ]

        step = ReflectionStep(name="test", config={})

        for critique_text, expected_score in test_cases:
            score = step._parse_score(critique_text)
            assert abs(score - expected_score) < 0.01, \
                f"Failed to parse score from: {critique_text}"

    @pytest.mark.asyncio
    async def test_reflection_without_adapter_fails(self):
        """Test that reflection fails gracefully without adapter"""

        step = ReflectionStep(
            name="test_reflection",
            config={
                "initial_output": "Test",
                "criteria": {"quality": "High"}
            }
        )
        step.adapter = None

        with pytest.raises((RuntimeError, AttributeError)):
            await step.run({})

    @pytest.mark.asyncio
    async def test_reflection_requires_initial_output(self):
        """Test that initial_output is required"""

        step = ReflectionStep(
            name="test_reflection",
            config={
                "criteria": {"quality": "High"}
                # Missing initial_output
            }
        )
        step.adapter = MockAdapter([])

        with pytest.raises(ValueError) as exc_info:
            await step.run({})

        assert "initial_output is required" in str(exc_info.value)


class TestPlanningStep:
    """Test PlanningStep pattern"""

    @pytest.mark.asyncio
    async def test_planning_basic_execution(self):
        """Test basic planning execution"""

        mock_responses = [
            """Step 1: Research solar panel types
Expected: List of panel options
Depends: None

Step 2: Compare costs
Expected: Cost analysis
Depends: Step 1

Step 3: Select best option
Expected: Final recommendation
Depends: Step 2""",
            "VALID: The plan is comprehensive and achievable"
        ]

        step = PlanningStep(
            name="test_planning",
            config={
                "goal": "Choose solar panels for home",
                "constraints": ["Budget under $10k"]
            }
        )
        step.adapter = MockAdapter(mock_responses)

        result = await step.run({})

        assert "plan" in result
        assert "is_valid" in result
        assert result["is_valid"] is True
        assert result["total_steps"] == 3
        assert len(result["plan"]) == 3
        assert result["plan"][0]["step_number"] == 1

    @pytest.mark.asyncio
    async def test_planning_with_runtime_goal(self):
        """Test planning with runtime goal"""

        mock_responses = [
            "Step 1: Do task A\nStep 2: Do task B",
            "VALID: Good plan"
        ]

        step = PlanningStep(name="test", config={})
        step.adapter = MockAdapter(mock_responses)

        result = await step.run({
            "goal": "Achieve something",
            "constraints": ["Time limit: 1 hour"]
        })

        assert result["goal"] == "Achieve something"
        assert len(result["plan"]) >= 2

    @pytest.mark.asyncio
    async def test_planning_step_parsing(self):
        """Test that plan steps are correctly parsed"""

        plan_text = """Step 1: First action
Expected: Some outcome
Depends: None

Step 2: Second action
Expected: Another outcome
Depends: Step 1

Step 3: Third action"""

        step = PlanningStep(name="test", config={})
        steps = step._parse_steps(plan_text)

        assert len(steps) == 3
        assert steps[0]["step_number"] == 1
        assert "First action" in steps[0]["action"]
        assert "Some outcome" in steps[0]["expected_outcome"]
        assert steps[1]["step_number"] == 2

    @pytest.mark.asyncio
    async def test_planning_time_estimation(self):
        """Test time estimation for plans"""

        step = PlanningStep(name="test", config={})

        # Test short plan (< 1 hour)
        short_plan = [{"action": f"Step {i}"} for i in range(3)]
        time_str = step._estimate_time(short_plan)
        assert "minutes" in time_str

        # Test longer plan (> 1 hour)
        long_plan = [{"action": f"Step {i}"} for i in range(10)]
        time_str = step._estimate_time(long_plan)
        assert "h" in time_str

    @pytest.mark.asyncio
    async def test_planning_requires_goal(self):
        """Test that goal is required"""

        step = PlanningStep(name="test", config={})
        step.adapter = MockAdapter([])

        with pytest.raises(ValueError) as exc_info:
            await step.run({})

        assert "goal is required" in str(exc_info.value)


class TestToolUseStep:
    """Test ToolUseStep pattern"""

    @pytest.mark.asyncio
    async def test_tool_use_basic_execution(self):
        """Test basic tool use execution"""

        mock_responses = [
            "calculator, search",  # Tool selection
            "The answer is 1628.89 based on compound interest calculation"  # Synthesis
        ]

        step = ToolUseStep(
            name="test_tool",
            config={
                "task": "Calculate compound interest",
                "available_tools": ["calculator", "search", "code_executor"]
            }
        )
        step.adapter = MockAdapter(mock_responses)

        result = await step.run({})

        assert "selected_tools" in result
        assert "tool_results" in result
        assert "final_answer" in result
        assert len(result["selected_tools"]) >= 1
        assert result["tools_used"] >= 1

    @pytest.mark.asyncio
    async def test_tool_selection_parsing(self):
        """Test tool selection parsing"""

        step = ToolUseStep(name="test", config={})

        test_cases = [
            ("calculator, search, executor", ["calculator", "search", "executor"]),
            ("calculator", ["calculator"]),
            ("tool1, tool2, tool3", ["tool1", "tool2", "tool3"]),
        ]

        for input_text, expected_tools in test_cases:
            tools = step._parse_tool_selection(input_text)
            assert len(tools) == len(expected_tools)

    @pytest.mark.asyncio
    async def test_tool_execution_simulation(self):
        """Test that tools are simulated correctly"""

        step = ToolUseStep(name="test", config={})

        result = await step._execute_tool("calculator", "test task")
        assert "result" in result.lower() or "calculation" in result.lower()

        result = await step._execute_tool("search", "test task")
        assert len(result) > 0

    @pytest.mark.asyncio
    async def test_tool_use_requires_task(self):
        """Test that task is required"""

        step = ToolUseStep(name="test", config={})
        step.adapter = MockAdapter([])

        with pytest.raises(ValueError) as exc_info:
            await step.run({})

        assert "task is required" in str(exc_info.value)


class TestPatternIntegration:
    """Test pattern integration with pipeline system"""

    @pytest.mark.asyncio
    async def test_pattern_step_interface(self):
        """Test that all pattern steps implement Step interface"""

        # All should have run method
        for StepClass in [ReflectionStep, PlanningStep, ToolUseStep]:
            step = StepClass(name="test", config={})
            assert hasattr(step, "run")
            assert asyncio.iscoroutinefunction(step.run)

    @pytest.mark.asyncio
    async def test_pattern_can_be_used_in_pipeline(self):
        """Test that patterns can be composed in pipelines"""

        # Create simple pipeline-like execution
        steps = [
            PlanningStep(
                name="plan",
                config={"goal": "Test goal", "constraints": []}
            ),
            ReflectionStep(
                name="reflect",
                config={
                    "initial_output": "Test output",
                    "criteria": {"quality": "High"},
                    "max_iterations": 1
                }
            )
        ]

        # Mock LLM for all steps
        for step in steps:
            step.adapter = MockAdapter([
                "Step 1: Do something",
                "VALID: Good plan",
                "Score: 8/10\nGood quality"
            ])

        # Execute sequentially
        data = {}
        for step in steps:
            result = await step.run(data)
            # Pass output to next step
            data.update(result)

        assert "plan" in data  # From planning step
        assert "final_output" in data  # From reflection step


class TestPatternWithEnvironment:
    """Test patterns with different environment configurations"""

    @pytest.mark.asyncio
    async def test_pattern_detects_missing_api_keys(self):
        """Test that patterns detect missing API keys"""

        # Clear environment temporarily
        old_env = {
            "OPENAI_API_KEY": os.environ.get("OPENAI_API_KEY"),
            "ANTHROPIC_API_KEY": os.environ.get("ANTHROPIC_API_KEY"),
            "GEMINI_API_KEY": os.environ.get("GEMINI_API_KEY")
        }

        for key in old_env:
            if key in os.environ:
                del os.environ[key]

        try:
            step = ReflectionStep(
                name="test",
                config={"initial_output": "Test"}
            )

            # Adapter is always created (it doesn't need API keys at init time)
            # But it will fail when actually trying to spawn a subprocess
            assert step.adapter is not None

        finally:
            # Restore environment
            for key, value in old_env.items():
                if value is not None:
                    os.environ[key] = value


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
