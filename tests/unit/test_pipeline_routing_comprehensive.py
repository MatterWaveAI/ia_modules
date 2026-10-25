"""
Comprehensive tests for pipeline/routing.py
"""
import pytest
import asyncio
from unittest.mock import MagicMock

from ia_modules.pipeline.routing import (
    RoutingContext,
    AgentConditionEvaluator,
    FunctionConditionEvaluator,
    ExpressionConditionEvaluator,
    AdvancedRouter,
    ParallelExecutor
)


class TestRoutingContext:
    """Test RoutingContext dataclass"""

    def test_routing_context_creation(self):
        """Test creating routing context"""
        context = RoutingContext(
            pipeline_data={"input": "test"},
            step_results={"step1": {"output": "result"}},
            current_step_id="step2",
            execution_id="exec-123"
        )

        assert context.pipeline_data == {"input": "test"}
        assert context.step_results == {"step1": {"output": "result"}}
        assert context.current_step_id == "step2"
        assert context.execution_id == "exec-123"
        assert context.metadata is None

    def test_routing_context_with_metadata(self):
        """Test routing context with metadata"""
        context = RoutingContext(
            pipeline_data={},
            step_results={},
            current_step_id="step1",
            execution_id="exec-456",
            metadata={"custom": "data"}
        )

        assert context.metadata == {"custom": "data"}


class TestAgentConditionEvaluator:
    """Test AgentConditionEvaluator class"""

    @pytest.fixture
    def sample_context(self):
        """Create sample routing context"""
        return RoutingContext(
            pipeline_data={"user_input": "test"},
            step_results={"validation": {"valid": True}},
            current_step_id="decision",
            execution_id="exec-789"
        )

    def test_init(self):
        """Test AgentConditionEvaluator initialization"""
        evaluator = AgentConditionEvaluator(
            model="gpt-4",
            prompt_template="Should we proceed? Context: {{context}}",
            context_fields=["user_input"],
            confidence_threshold=0.8
        )

        assert evaluator.model == "gpt-4"
        assert evaluator.confidence_threshold == 0.8
        assert evaluator.context_fields == ["user_input"]

    @pytest.mark.asyncio
    async def test_evaluate_success(self, sample_context):
        """Test successful agent evaluation"""
        evaluator = AgentConditionEvaluator(
            model="gpt-4",
            prompt_template="Proceed?"
        )

        result = await evaluator.evaluate(sample_context)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    async def test_evaluate_with_error_in_prompt(self, sample_context):
        """Test evaluation with error keyword in prompt"""
        evaluator = AgentConditionEvaluator(
            model="gpt-4",
            prompt_template="Check for error condition"
        )

        result = await evaluator.evaluate(sample_context)
        assert result is False  # Mock returns False for "error" keyword

    def test_build_agent_context_with_fields(self, sample_context):
        """Test building agent context with specific fields"""
        evaluator = AgentConditionEvaluator(
            model="gpt-4",
            prompt_template="Test",
            context_fields=["user_input", "validation"]
        )

        agent_context = evaluator._build_agent_context(sample_context)

        assert "user_input" in agent_context
        assert agent_context["user_input"] == "test"
        assert "validation" in agent_context

    def test_build_agent_context_without_fields(self, sample_context):
        """Test building agent context without specific fields"""
        evaluator = AgentConditionEvaluator(
            model="gpt-4",
            prompt_template="Test"
        )

        agent_context = evaluator._build_agent_context(sample_context)

        assert "step_results" in agent_context
        assert "pipeline_data" in agent_context

    def test_parse_agent_response_yes(self):
        """Test parsing 'yes' response"""
        evaluator = AgentConditionEvaluator(
            model="gpt-4",
            prompt_template="Test",
            confidence_threshold=0.7
        )

        response = {"response": "yes", "confidence": 0.9}
        result = evaluator._parse_agent_response(response)
        assert result is True

    def test_parse_agent_response_no(self):
        """Test parsing 'no' response"""
        evaluator = AgentConditionEvaluator(
            model="gpt-4",
            prompt_template="Test",
            confidence_threshold=0.7
        )

        response = {"response": "no", "confidence": 0.8}
        result = evaluator._parse_agent_response(response)
        assert result is False

    def test_parse_agent_response_low_confidence(self):
        """Test parsing response with low confidence"""
        evaluator = AgentConditionEvaluator(
            model="gpt-4",
            prompt_template="Test",
            confidence_threshold=0.9
        )

        response = {"response": "yes", "confidence": 0.5}
        with pytest.raises(ValueError, match="confidence.*below threshold"):
            evaluator._parse_agent_response(response)

    def test_parse_agent_response_unexpected(self):
        """Test parsing unexpected response"""
        evaluator = AgentConditionEvaluator(
            model="gpt-4",
            prompt_template="Test"
        )

        response = {"response": "maybe", "confidence": 0.9}
        with pytest.raises(ValueError, match="Unexpected agent response"):
            evaluator._parse_agent_response(response)


class TestFunctionConditionEvaluator:
    """Test FunctionConditionEvaluator class"""

    @pytest.fixture
    def sample_context(self):
        """Create sample routing context"""
        return RoutingContext(
            pipeline_data={"value": 42},
            step_results={},
            current_step_id="check",
            execution_id="exec-func"
        )

    def test_init(self):
        """Test FunctionConditionEvaluator initialization"""
        evaluator = FunctionConditionEvaluator(
            function_name="check_condition",
            module_path="my.module",
            parameters={"threshold": 10},
            timeout_seconds=60
        )

        assert evaluator.function_name == "check_condition"
        assert evaluator.module_path == "my.module"
        assert evaluator.parameters == {"threshold": 10}
        assert evaluator.timeout_seconds == 60

    @pytest.mark.asyncio
    async def test_evaluate_success(self, sample_context):
        """Test successful function evaluation"""
        def mock_function(context, parameters):
            return True

        evaluator = FunctionConditionEvaluator(
            function_name="test_func",
            module_path="test.module"
        )
        evaluator._function = mock_function

        result = await evaluator.evaluate(sample_context)
        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_returns_truthy(self, sample_context):
        """Test function returning truthy value"""
        def mock_function(context, parameters):
            return "non-empty string"

        evaluator = FunctionConditionEvaluator(
            function_name="test_func",
            module_path="test.module"
        )
        evaluator._function = mock_function

        result = await evaluator.evaluate(sample_context)
        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_returns_falsy(self, sample_context):
        """Test function returning falsy value"""
        def mock_function(context, parameters):
            return 0

        evaluator = FunctionConditionEvaluator(
            function_name="test_func",
            module_path="test.module"
        )
        evaluator._function = mock_function

        result = await evaluator.evaluate(sample_context)
        assert result is False

    def test_prepare_arguments(self, sample_context):
        """Test preparing function arguments"""
        evaluator = FunctionConditionEvaluator(
            function_name="test",
            module_path="test",
            parameters={"key": "value"}
        )

        args = evaluator._prepare_arguments(sample_context)

        assert "context" in args
        assert "parameters" in args
        assert args["context"] == sample_context
        assert args["parameters"] == {"key": "value"}


class TestExpressionConditionEvaluator:
    """Test ExpressionConditionEvaluator class"""

    @pytest.fixture
    def sample_context(self):
        """Create sample routing context"""
        return RoutingContext(
            pipeline_data={"count": 10, "status": "active"},
            step_results={"validation": {"score": 85}},
            current_step_id="check",
            execution_id="exec-expr"
        )

    def test_init(self):
        """Test ExpressionConditionEvaluator initialization"""
        evaluator = ExpressionConditionEvaluator(
            source="count",
            operator="==",
            value=10
        )

        assert evaluator.source == "count"
        assert evaluator.operator == "=="
        assert evaluator.value == 10

    @pytest.mark.asyncio
    async def test_evaluate_equals(self, sample_context):
        """Test equality operator"""
        evaluator = ExpressionConditionEvaluator(
            source="count",
            operator="==",
            value=10
        )

        result = await evaluator.evaluate(sample_context)
        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_not_equals(self, sample_context):
        """Test not equals operator"""
        evaluator = ExpressionConditionEvaluator(
            source="count",
            operator="!=",
            value=5
        )

        result = await evaluator.evaluate(sample_context)
        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_greater_than(self, sample_context):
        """Test greater than operator"""
        evaluator = ExpressionConditionEvaluator(
            source="count",
            operator=">",
            value=5
        )

        result = await evaluator.evaluate(sample_context)
        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_less_than_or_equal(self, sample_context):
        """Test less than or equal operator"""
        evaluator = ExpressionConditionEvaluator(
            source="count",
            operator="<=",
            value=10
        )

        result = await evaluator.evaluate(sample_context)
        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_in_operator(self, sample_context):
        """Test 'in' operator"""
        evaluator = ExpressionConditionEvaluator(
            source="status",
            operator="in",
            value=["active", "pending"]
        )

        result = await evaluator.evaluate(sample_context)
        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_contains(self, sample_context):
        """Test contains operator"""
        evaluator = ExpressionConditionEvaluator(
            source="status",
            operator="contains",
            value="act"
        )

        result = await evaluator.evaluate(sample_context)
        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_startswith(self, sample_context):
        """Test startswith operator"""
        evaluator = ExpressionConditionEvaluator(
            source="status",
            operator="startswith",
            value="act"
        )

        result = await evaluator.evaluate(sample_context)
        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_nested_path(self, sample_context):
        """Test extracting nested value"""
        evaluator = ExpressionConditionEvaluator(
            source="step_results.validation.score",
            operator=">",
            value=80
        )

        result = await evaluator.evaluate(sample_context)
        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_unsupported_operator(self, sample_context):
        """Test unsupported operator"""
        evaluator = ExpressionConditionEvaluator(
            source="count",
            operator="%%%",
            value=10
        )

        with pytest.raises(ValueError, match="Unsupported operator"):
            await evaluator.evaluate(sample_context)

    @pytest.mark.asyncio
    async def test_extract_value_not_found(self, sample_context):
        """Test extracting non-existent value"""
        evaluator = ExpressionConditionEvaluator(
            source="nonexistent",
            operator="==",
            value=10
        )

        with pytest.raises(KeyError):
            await evaluator.evaluate(sample_context)


class TestAdvancedRouter:
    """Test AdvancedRouter class"""

    @pytest.fixture
    def sample_context(self):
        """Create sample routing context"""
        return RoutingContext(
            pipeline_data={"status": "ready"},
            step_results={},
            current_step_id="step1",
            execution_id="exec-router"
        )

    def test_init(self):
        """Test AdvancedRouter initialization"""
        router = AdvancedRouter()

        assert "expression" in router.evaluators
        assert "agent" in router.evaluators
        assert "function" in router.evaluators

    @pytest.mark.asyncio
    async def test_evaluate_condition_always(self, sample_context):
        """Test 'always' condition type"""
        router = AdvancedRouter()

        result = await router.evaluate_condition("always", {}, sample_context)
        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_condition_expression(self, sample_context):
        """Test expression condition evaluation"""
        router = AdvancedRouter()

        config = {
            "source": "status",
            "operator": "==",
            "value": "ready"
        }

        result = await router.evaluate_condition("expression", config, sample_context)
        assert result is True

    @pytest.mark.asyncio
    async def test_evaluate_condition_unknown_type(self, sample_context):
        """Test unknown condition type"""
        router = AdvancedRouter()

        with pytest.raises(ValueError, match="Unknown condition type"):
            await router.evaluate_condition("unknown", {}, sample_context)

    @pytest.mark.asyncio
    async def test_find_next_steps_single_path(self, sample_context):
        """Test finding next steps with single matching path"""
        router = AdvancedRouter()

        flow_paths = [
            {
                "from": "step1",
                "to": "step2",
                "condition": {"type": "always"}
            }
        ]

        next_steps = await router.find_next_steps("step1", flow_paths, sample_context)
        assert next_steps == ["step2"]

    @pytest.mark.asyncio
    async def test_find_next_steps_multiple_paths(self, sample_context):
        """Test finding next steps with multiple matching paths"""
        router = AdvancedRouter()

        flow_paths = [
            {
                "from": "step1",
                "to": "step2a",
                "condition": {"type": "always"}
            },
            {
                "from": "step1",
                "to": "step2b",
                "condition": {"type": "always"}
            }
        ]

        next_steps = await router.find_next_steps("step1", flow_paths, sample_context)
        assert len(next_steps) == 2
        assert "step2a" in next_steps
        assert "step2b" in next_steps

    @pytest.mark.asyncio
    async def test_find_next_steps_no_match(self, sample_context):
        """Test finding next steps with no matching paths"""
        router = AdvancedRouter()

        flow_paths = [
            {
                "from": "step2",
                "to": "step3",
                "condition": {"type": "always"}
            }
        ]

        next_steps = await router.find_next_steps("step1", flow_paths, sample_context)
        assert next_steps == []

    @pytest.mark.asyncio
    async def test_find_next_steps_condition_fails(self, sample_context):
        """Test finding next steps when condition fails"""
        router = AdvancedRouter()

        flow_paths = [
            {
                "from": "step1",
                "to": "step2",
                "condition": {
                    "type": "expression",
                    "config": {
                        "source": "status",
                        "operator": "==",
                        "value": "not_ready"
                    }
                }
            }
        ]

        next_steps = await router.find_next_steps("step1", flow_paths, sample_context)
        assert next_steps == []


class TestParallelExecutor:
    """Test ParallelExecutor class"""

    def test_init(self):
        """Test ParallelExecutor initialization"""
        executor = ParallelExecutor(max_workers=8)

        assert executor.max_workers == 8
        assert executor.active_tasks == {}

    @pytest.mark.asyncio
    async def test_execute_parallel_steps_single_step(self):
        """Test executing single step (no parallelization)"""
        async def mock_executor(step_id, context):
            return {"step": step_id, "result": "done"}

        context = RoutingContext(
            pipeline_data={},
            step_results={},
            current_step_id="step1",
            execution_id="exec-123"
        )

        executor = ParallelExecutor()
        result = await executor.execute_parallel_steps(
            ["step1"],
            mock_executor,
            context
        )

        assert result["step"] == "step1"

    @pytest.mark.asyncio
    async def test_execute_parallel_steps_empty_list(self):
        """Test executing with empty step list"""
        async def mock_executor(step_id, context):
            return {}

        context = RoutingContext(
            pipeline_data={},
            step_results={},
            current_step_id="step1",
            execution_id="exec-123"
        )

        executor = ParallelExecutor()
        result = await executor.execute_parallel_steps([], mock_executor, context)

        assert result == {}

    @pytest.mark.asyncio
    async def test_execute_parallel_steps_multiple(self):
        """Test executing multiple steps in parallel"""
        async def mock_executor(step_id, context):
            await asyncio.sleep(0.01)
            return {"step": step_id, "completed": True}

        context = RoutingContext(
            pipeline_data={},
            step_results={},
            current_step_id="step1",
            execution_id="exec-123"
        )

        executor = ParallelExecutor()
        results = await executor.execute_parallel_steps(
            ["step2", "step3", "step4"],
            mock_executor,
            context
        )

        assert len(results) == 3
        assert all(results[step]["completed"] for step in ["step2", "step3", "step4"])

    @pytest.mark.asyncio
    async def test_execute_parallel_steps_with_error(self):
        """Test executing parallel steps with one failing"""
        async def mock_executor(step_id, context):
            if step_id == "failing_step":
                raise ValueError("Step failed")
            return {"step": step_id, "completed": True}

        context = RoutingContext(
            pipeline_data={},
            step_results={},
            current_step_id="step1",
            execution_id="exec-123"
        )

        executor = ParallelExecutor()
        results = await executor.execute_parallel_steps(
            ["good_step", "failing_step"],
            mock_executor,
            context
        )

        assert results["good_step"]["completed"] is True
        assert "error" in results["failing_step"]
        assert results["failing_step"]["status"] == "failed"

    @pytest.mark.asyncio
    async def test_cancel_all_tasks(self):
        """Test canceling all active tasks"""
        async def long_running_executor(step_id, context):
            await asyncio.sleep(10)
            return {"step": step_id}

        context = RoutingContext(
            pipeline_data={},
            step_results={},
            current_step_id="step1",
            execution_id="exec-123"
        )

        executor = ParallelExecutor()

        # Start parallel execution but don't await
        task = asyncio.create_task(
            executor.execute_parallel_steps(
                ["step1", "step2"],
                long_running_executor,
                context
            )
        )

        # Give it time to start
        await asyncio.sleep(0.01)

        # Cancel all tasks
        executor.cancel_all_tasks()

        assert len(executor.active_tasks) == 0

        # Clean up
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass

    def test_get_active_step_count(self):
        """Test getting active step count"""
        executor = ParallelExecutor()

        # Create mock tasks
        task1 = MagicMock()
        task1.done.return_value = False
        task2 = MagicMock()
        task2.done.return_value = True

        executor.active_tasks = {"step1": task1, "step2": task2}

        count = executor.get_active_step_count()
        assert count == 1  # Only one not done
