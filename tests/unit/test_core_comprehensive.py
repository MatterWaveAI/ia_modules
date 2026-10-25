"""
Comprehensive unit tests for pipeline/core.py

Tests TemplateParameterResolver, InputResolver, Step, and Pipeline classes
"""

import pytest
from unittest.mock import Mock, AsyncMock

from ia_modules.pipeline.core import (
    TemplateParameterResolver,
    InputResolver,
    Step,
    Pipeline,
    run_pipeline
)
from ia_modules.pipeline.services import ServiceRegistry
from ia_modules.pipeline.errors import PipelineError, ErrorCategory, ErrorSeverity
from ia_modules.pipeline.test_utils import create_test_execution_context


class MockStep(Step):
    """Mock step for testing"""

    def __init__(self, name: str, config: dict, behavior: callable = None):
        super().__init__(name, config)
        self.behavior = behavior or self._default_behavior

    async def _default_behavior(self, data: dict) -> dict:
        return {"result": "success", "input": data}

    async def run(self, data: dict) -> dict:
        return await self.behavior(data)


class TestTemplateParameterResolver:
    """Test TemplateParameterResolver"""

    def test_resolve_parameters_string(self):
        """Test resolving string template"""
        config = {
            "message": "Hello {{ parameters.name }}"
        }
        context = {"parameters": {"name": "World"}}

        result = TemplateParameterResolver.resolve_parameters(config, context)

        assert result["message"] == "Hello World"

    def test_resolve_parameters_nested_dict(self):
        """Test resolving nested dictionary"""
        config = {
            "outer": {
                "inner": "Value: {{ parameters.value }}"
            }
        }
        context = {"parameters": {"value": "42"}}

        result = TemplateParameterResolver.resolve_parameters(config, context)

        assert result["outer"]["inner"] == "Value: 42"

    def test_resolve_parameters_list(self):
        """Test resolving list with templates"""
        config = {
            "items": [
                "Item {{ parameters.num }}",
                "Another {{ parameters.text }}"
            ]
        }
        context = {"parameters": {"num": "1", "text": "test"}}

        result = TemplateParameterResolver.resolve_parameters(config, context)

        assert result["items"][0] == "Item 1"
        assert result["items"][1] == "Another test"

    def test_resolve_parameters_no_template(self):
        """Test resolving config without templates"""
        config = {"key": "value"}
        context = {}

        result = TemplateParameterResolver.resolve_parameters(config, context)

        assert result == config

    def test_resolve_parameters_missing_parameter(self):
        """A template naming a parameter the run was not given is an error, not a literal"""
        config = {"message": "Hello {{ parameters.missing }}"}
        context = {"parameters": {}}

        with pytest.raises(ValueError, match="parameter 'missing' was not provided"):
            TemplateParameterResolver.resolve_parameters(config, context)


class TestInputResolver:
    """Test InputResolver"""

    def test_resolve_step_inputs_from_parameters(self):
        """Test resolving input from parameters"""
        inputs = [
            {"name": "param1", "source": "{parameters.value1}"}
        ]
        context = {"parameters": {"value1": "test"}}

        result = InputResolver.resolve_step_inputs(inputs, context)

        assert result["param1"] == "test"

    def test_resolve_step_inputs_from_pipeline_input(self):
        """Test resolving input from pipeline input"""
        inputs = [
            {"name": "data", "source": "{pipeline_input}"}
        ]
        context = {"pipeline_input": {"key": "value"}}

        result = InputResolver.resolve_step_inputs(inputs, context)

        assert result["data"] == {"key": "value"}

    def test_resolve_step_inputs_from_step_output(self):
        """Test resolving input from step output"""
        inputs = [
            {"name": "result", "source": "{steps.step1.output.data}"}
        ]
        context = {
            "steps": {
                "step1": {"data": "step1_result"}
            }
        }

        result = InputResolver.resolve_step_inputs(inputs, context)

        assert result["result"] == "step1_result"

    def test_resolve_step_inputs_literal_value(self):
        """Test resolving literal value (no template)"""
        inputs = [
            {"name": "literal", "source": "plain_value"}
        ]
        context = {}

        result = InputResolver.resolve_step_inputs(inputs, context)

        assert result["literal"] == "plain_value"

    def test_resolve_step_inputs_multiple(self):
        """Test resolving multiple inputs"""
        inputs = [
            {"name": "param", "source": "{parameters.value}"},
            {"name": "literal", "source": "test"}
        ]
        context = {"parameters": {"value": "param_value"}}

        result = InputResolver.resolve_step_inputs(inputs, context)

        assert result["param"] == "param_value"
        assert result["literal"] == "test"


class TestStepInit:
    """Test Step initialization"""

    def test_step_init_minimal(self):
        """Test step initialization with minimal config"""
        step = MockStep("test", {})

        assert step.name == "test"
        assert step.config == {}
        assert step.continue_on_error is False
        assert step.enable_fallback is False
        assert step.retry_config is None

    def test_step_init_with_error_handling(self):
        """Test step with error handling config"""
        config = {
            "error_handling": {
                "continue_on_error": True,
                "enable_fallback": True
            }
        }
        step = MockStep("test", config)

        assert step.continue_on_error is True
        assert step.enable_fallback is True

    def test_step_init_with_retry_config(self):
        """Test step with retry configuration"""
        config = {
            "error_handling": {
                "retry": {
                    "max_attempts": 3,
                    "initial_delay": 1.0,
                    "max_delay": 10.0,
                    "exponential_base": 2.0
                }
            }
        }
        step = MockStep("test", config)

        assert step.retry_config is not None
        assert step.retry_config.max_attempts == 3


class TestStepServices:
    """Test step service access"""

    def test_get_db_with_services(self):
        """Test getting database service"""
        step = MockStep("test", {})
        mock_db = Mock()
        mock_services = Mock()
        mock_services.get = Mock(return_value=mock_db)

        step.services = mock_services

        db = step.get_db()

        assert db == mock_db
        mock_services.get.assert_called_with('database')

    def test_get_db_without_services(self):
        """Test getting database when no services"""
        step = MockStep("test", {})

        db = step.get_db()

        assert db is None

    def test_get_http_with_services(self):
        """Test getting HTTP client service"""
        step = MockStep("test", {})
        mock_http = Mock()
        mock_services = Mock()
        mock_services.get = Mock(return_value=mock_http)

        step.services = mock_services

        http = step.get_http()

        assert http == mock_http
        mock_services.get.assert_called_with('http')


class TestStepErrorHandling:
    """Test step error handling"""

    @pytest.mark.asyncio
    async def test_execute_with_error_handling_success(self):
        """Test successful execution"""
        step = MockStep("test", {})

        result = await step.execute_with_error_handling({"input": "data"})

        assert result["result"] == "success"

    @pytest.mark.asyncio
    async def test_execute_with_continue_on_error(self):
        """Test execution with continue_on_error"""

        async def failing_behavior(data):
            raise ValueError("Step failed")

        config = {"error_handling": {"continue_on_error": True}}
        step = MockStep("test", config, behavior=failing_behavior)

        result = await step.execute_with_error_handling({"input": "data"})

        assert result["step_error"] is True
        assert "Step failed" in result["error_message"]
        assert result["step_name"] == "test"

    @pytest.mark.asyncio
    async def test_execute_without_continue_on_error_raises(self):
        """Test execution without continue_on_error raises"""

        async def failing_behavior(data):
            raise ValueError("Step failed")

        step = MockStep("test", {}, behavior=failing_behavior)

        with pytest.raises(PipelineError):
            await step.execute_with_error_handling({"input": "data"})

    @pytest.mark.asyncio
    async def test_fallback_default_raises(self):
        """Test default fallback raises error"""
        step = MockStep("test", {})
        error = PipelineError("Test error", category=ErrorCategory.VALIDATION, severity=ErrorSeverity.ERROR)

        with pytest.raises(PipelineError):
            await step.fallback({"data": "test"}, error)


class TestPipelineInit:
    """Test Pipeline initialization"""

    def test_pipeline_init_minimal(self):
        """Test pipeline initialization with minimal config"""
        steps = [MockStep("step1", {})]
        flow = {"start_at": "step1", "paths": []}
        services = ServiceRegistry()

        pipeline = Pipeline("test", steps, flow, services)

        assert pipeline.name == "test"
        assert len(pipeline.steps) == 1
        assert pipeline.enable_telemetry is True

    def test_pipeline_init_without_telemetry(self):
        """Test pipeline without telemetry"""
        steps = [MockStep("step1", {})]
        flow = {"start_at": "step1", "paths": []}
        services = ServiceRegistry()

        pipeline = Pipeline("test", steps, flow, services, enable_telemetry=False)

        assert pipeline.enable_telemetry is False
        assert pipeline.telemetry is None

    def test_pipeline_init_injects_services(self):
        """Test pipeline injects services into steps"""
        steps = [MockStep("step1", {}), MockStep("step2", {})]
        flow = {"start_at": "step1", "paths": []}
        services = ServiceRegistry()

        Pipeline("test", steps, flow, services)

        assert steps[0].services == services
        assert steps[1].services == services

    def test_pipeline_init_creates_step_map(self):
        """Test pipeline creates step mapping"""
        steps = [MockStep("step1", {}), MockStep("step2", {})]
        flow = {"start_at": "step1", "paths": []}
        services = ServiceRegistry()

        pipeline = Pipeline("test", steps, flow, services)

        assert "step1" in pipeline.step_map
        assert "step2" in pipeline.step_map


class TestPipelineLoopDetection:
    """Test pipeline loop detection"""

    def test_pipeline_has_loops_false(self):
        """Test has_loops returns False when no loops"""
        steps = [MockStep("step1", {})]
        flow = {"start_at": "step1", "paths": []}
        services = ServiceRegistry()

        pipeline = Pipeline("test", steps, flow, services)

        assert pipeline.has_loops() is False

    def test_pipeline_get_loops_empty(self):
        """Test get_loops returns empty when no detector"""
        steps = [MockStep("step1", {})]
        flow = {"start_at": "step1", "paths": []}
        services = ServiceRegistry()

        pipeline = Pipeline("test", steps, flow, services)

        assert pipeline.get_loops() == []


class TestPipelineBuildExecutionPath:
    """Test execution path building"""

    def test_build_execution_path_single_step(self):
        """Test building path with single step"""
        steps = [MockStep("step1", {})]
        flow = {"start_at": "step1", "paths": []}
        services = ServiceRegistry()

        pipeline = Pipeline("test", steps, flow, services)
        path = pipeline._build_execution_path()

        assert path == ["step1"]

    def test_build_execution_path_sequential(self):
        """Test building path with sequential steps"""
        steps = [MockStep("step1", {}), MockStep("step2", {})]
        flow = {
            "start_at": "step1",
            "paths": [
                {"from": "step1", "to": "step2"}
            ]
        }
        services = ServiceRegistry()

        pipeline = Pipeline("test", steps, flow, services)
        path = pipeline._build_execution_path()

        assert path == ["step1", "step2"]

    def test_build_execution_path_skips_end_markers(self):
        """Test building path skips end markers"""
        steps = [MockStep("step1", {})]
        flow = {
            "start_at": "step1",
            "paths": [
                {"from": "step1", "to": "end_with_success"}
            ]
        }
        services = ServiceRegistry()

        pipeline = Pipeline("test", steps, flow, services)
        path = pipeline._build_execution_path()

        assert path == ["step1"]
        assert "end_with_success" not in path


class TestPipelineRun:
    """Test pipeline execution"""

    @pytest.mark.asyncio
    async def test_run_single_step(self):
        """Test running pipeline with single step"""
        steps = [MockStep("step1", {})]
        flow = {"start_at": "step1", "paths": []}
        services = ServiceRegistry()

        pipeline = Pipeline("test", steps, flow, services, enable_telemetry=False)

        result = await pipeline.run({"input": "data"}, create_test_execution_context())

        # Verify basic structure
        assert "input" in result
        assert len(result["steps"]) == 1
        assert result["steps"][0]["step_name"] == "step1"
        assert result["output"] is not None
        assert "result" in result["output"]

    @pytest.mark.asyncio
    async def test_run_sequential_steps(self):
        """Test running pipeline with sequential steps"""
        steps = [MockStep("step1", {}), MockStep("step2", {})]
        flow = {
            "start_at": "step1",
            "paths": [
                {"from": "step1", "to": "step2"}
            ]
        }
        services = ServiceRegistry()

        pipeline = Pipeline("test", steps, flow, services, enable_telemetry=False)

        result = await pipeline.run({"input": "data"}, create_test_execution_context())

        assert len(result["steps"]) == 2
        assert result["steps"][0]["step_name"] == "step1"
        assert result["steps"][1]["step_name"] == "step2"

    @pytest.mark.asyncio
    async def test_run_no_start_step_raises(self):
        """Test run raises when no start step"""
        steps = [MockStep("step1", {})]
        flow = {"paths": []}  # Missing start_at
        services = ServiceRegistry()

        pipeline = Pipeline("test", steps, flow, services, enable_telemetry=False)

        with pytest.raises(ValueError, match="No start step"):
            await pipeline.run({"input": "data"}, create_test_execution_context())


class TestPipelineResume:
    """Test pipeline resume functionality"""

    @pytest.mark.asyncio
    async def test_resume_without_checkpointer_raises(self):
        """Test resume raises without checkpointer"""
        steps = [MockStep("step1", {})]
        flow = {"start_at": "step1", "paths": []}
        services = ServiceRegistry()

        pipeline = Pipeline("test", steps, flow, services, enable_telemetry=False)

        with pytest.raises(ValueError, match="checkpointer not configured"):
            await pipeline.resume("thread-123")

    @pytest.mark.asyncio
    async def test_resume_no_checkpoint_found_raises(self):
        """Test resume raises when no checkpoint found"""
        steps = [MockStep("step1", {})]
        flow = {"start_at": "step1", "paths": []}
        services = ServiceRegistry()

        mock_checkpointer = Mock()
        mock_checkpointer.load_checkpoint = AsyncMock(return_value=None)

        pipeline = Pipeline("test", steps, flow, services, enable_telemetry=False, checkpointer=mock_checkpointer)

        with pytest.raises(ValueError, match="No checkpoint found"):
            await pipeline.resume("thread-123")


class TestRunPipelineFactory:
    """Test run_pipeline factory function"""

    def test_run_pipeline_creates_instance(self):
        """Test factory creates Pipeline instance"""
        steps = [MockStep("step1", {})]
        flow = {"start_at": "step1", "paths": []}
        services = ServiceRegistry()

        pipeline = run_pipeline("test", steps, flow, services)

        assert isinstance(pipeline, Pipeline)
        assert pipeline.name == "test"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
