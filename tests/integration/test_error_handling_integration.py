"""
Integration tests for error handling in pipeline execution
"""

import pytest
from typing import Dict, Any

from ia_modules.pipeline.core import Step, Pipeline
from ia_modules.pipeline.test_utils import create_test_execution_context
from ia_modules.pipeline.services import ServiceRegistry
from ia_modules.pipeline.errors import (
    NetworkError,
    ValidationError,
    ErrorCategory
)


class FlakyNetworkStep(Step):
    """Step that fails network calls but eventually succeeds"""

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self.attempt_count = 0
        self.fail_times = config.get('fail_times', 2)

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        self.attempt_count += 1

        if self.attempt_count <= self.fail_times:
            raise NetworkError(
                f"Network call failed (attempt {self.attempt_count})",
                step_id=self.name
            )

        return {
            "status": "success",
            "attempts": self.attempt_count,
            "message": "Network call succeeded"
        }


class StepWithFallback(Step):
    """Step with fallback mechanism"""

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # Always fails
        raise NetworkError("Primary source unavailable", step_id=self.name)

    async def fallback(self, data: Dict[str, Any], error) -> Dict[str, Any]:
        # Return cached data
        return {
            "status": "success_from_fallback",
            "source": "cache",
            "data": "cached_value"
        }


class ValidationStep(Step):
    """Step that validates input data"""

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        required_field = self.config.get('required_field', 'value')

        if required_field not in data:
            raise ValidationError(
                f"Missing required field: {required_field}",
                step_id=self.name,
                field=required_field
            )

        return {"validated": True, "value": data[required_field]}


class ContinueOnErrorStep(Step):
    """Step that continues pipeline even on error"""

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        # Always fails
        raise NetworkError("This step always fails", step_id=self.name)


class TestErrorHandlingIntegration:
    """Integration tests for error handling"""

    @pytest.mark.asyncio
    async def test_retry_with_eventual_success(self):
        """Test step retries and eventually succeeds"""
        config = {
            'fail_times': 2,
            'error_handling': {
                'retry': {
                    'max_attempts': 3,
                    'initial_delay': 0.01,
                    'jitter': False
                }
            }
        }

        step = FlakyNetworkStep("flaky_step", config)
        step.services = ServiceRegistry()

        result = await step.execute_with_error_handling({"input": "data"})

        assert result["status"] == "success"
        assert result["attempts"] == 3
        assert step.attempt_count == 3

    @pytest.mark.asyncio
    async def test_retry_exhausted_raises_error(self):
        """Test that exhausted retries raise error"""
        config = {
            'fail_times': 5,  # More than max_attempts
            'error_handling': {
                'retry': {
                    'max_attempts': 3,
                    'initial_delay': 0.01
                }
            }
        }

        step = FlakyNetworkStep("flaky_step", config)
        step.services = ServiceRegistry()

        with pytest.raises(NetworkError):
            await step.execute_with_error_handling({"input": "data"})

        assert step.attempt_count == 3

    @pytest.mark.asyncio
    async def test_fallback_mechanism(self):
        """Test fallback mechanism when primary fails"""
        config = {
            'error_handling': {
                'enable_fallback': True
            }
        }

        step = StepWithFallback("fallback_step", config)
        step.services = ServiceRegistry()

        result = await step.execute_with_error_handling({"input": "data"})

        assert result["status"] == "success_from_fallback"
        assert result["source"] == "cache"
        assert result["data"] == "cached_value"

    @pytest.mark.asyncio
    async def test_non_retryable_error_fails_immediately(self):
        """Test that validation errors don't retry"""
        config = {
            'required_field': 'missing_field',
            'error_handling': {
                'retry': {
                    'max_attempts': 3
                }
            }
        }

        step = ValidationStep("validation_step", config)
        step.services = ServiceRegistry()

        # ValidationError is not retryable, should fail immediately
        with pytest.raises(ValidationError):
            await step.execute_with_error_handling({"wrong_field": "value"})

    @pytest.mark.asyncio
    async def test_continue_on_error(self):
        """Test continue_on_error flag"""
        config = {
            'error_handling': {
                'continue_on_error': True
            }
        }

        step = ContinueOnErrorStep("continue_step", config)
        step.services = ServiceRegistry()

        result = await step.execute_with_error_handling({"input": "data"})

        # Should return error state instead of raising
        assert result["step_error"] is True
        assert result["error_category"] == ErrorCategory.NETWORK.value
        assert result["step_name"] == "continue_step"
        assert "original_data" in result

    @pytest.mark.asyncio
    async def test_pipeline_with_retrying_step(self):
        """Test full pipeline with retrying step"""
        # Create pipeline with flaky step
        flaky_step = FlakyNetworkStep(
            "flaky",
            {
                'fail_times': 1,
                'error_handling': {
                    'retry': {
                        'max_attempts': 3,
                        'initial_delay': 0.01
                    }
                }
            }
        )

        class SuccessStep(Step):
            async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
                return {"final": "success", "from_flaky": data}

        success_step = SuccessStep("success", {})

        pipeline = Pipeline(
            name="test_pipeline",
            steps=[flaky_step, success_step],
            flow={
                "start_at": "flaky",
                "paths": [
                    {"from": "flaky", "to": "success"}
                ]
            },
            services=ServiceRegistry()
        )

        result = await pipeline.run({"input": "test"}, create_test_execution_context())

        # Flaky step should have succeeded after retries
        flaky_step_result = next(s for s in result["steps"] if s["step_name"] == "flaky")
        assert flaky_step_result["status"] == "completed"
        assert flaky_step_result["result"]["attempts"] == 2

        # Success step should have received flaky's output
        success_step_result = next(s for s in result["steps"] if s["step_name"] == "success")
        assert success_step_result["result"]["final"] == "success"

    @pytest.mark.asyncio
    async def test_pipeline_with_fallback_step(self):
        """Test pipeline with step using fallback"""
        fallback_step = StepWithFallback(
            "fallback",
            {'error_handling': {'enable_fallback': True}}
        )

        class ProcessStep(Step):
            async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
                return {"processed": data.get("data", "none")}

        process_step = ProcessStep("process", {})

        pipeline = Pipeline(
            name="fallback_pipeline",
            steps=[fallback_step, process_step],
            flow={
                "start_at": "fallback",
                "paths": [
                    {"from": "fallback", "to": "process"}
                ]
            },
            services=ServiceRegistry()
        )

        result = await pipeline.run({"input": "test"}, create_test_execution_context())

        # Fallback step should have used fallback
        fallback_step_result = next(s for s in result["steps"] if s["step_name"] == "fallback")
        assert fallback_step_result["status"] == "completed"
        assert fallback_step_result["result"]["source"] == "cache"

        # Process step should have received fallback data
        process_step_result = next(s for s in result["steps"] if s["step_name"] == "process")
        assert process_step_result["result"]["processed"] == "cached_value"

    @pytest.mark.asyncio
    async def test_mixed_error_strategies(self):
        """Test pipeline with mixed error handling strategies"""
        # Step 1: Retries
        retry_step = FlakyNetworkStep(
            "retry",
            {
                'fail_times': 1,
                'error_handling': {
                    'retry': {'max_attempts': 3, 'initial_delay': 0.01}
                }
            }
        )

        # Step 2: Continue on error
        continue_step = ContinueOnErrorStep(
            "continue",
            {'error_handling': {'continue_on_error': True}}
        )

        # Step 3: Normal step
        class FinalStep(Step):
            async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
                return {
                    "completed": True,
                    "had_error": data.get("step_error", False)
                }

        final_step = FinalStep("final", {})

        pipeline = Pipeline(
            name="mixed_pipeline",
            steps=[retry_step, continue_step, final_step],
            flow={
                "start_at": "retry",
                "paths": [
                    {"from": "retry", "to": "continue"},
                    {"from": "continue", "to": "final"}
                ]
            },
            services=ServiceRegistry()
        )

        result = await pipeline.run({"input": "test"}, create_test_execution_context())

        # Retry step succeeded
        retry_step_result = next(s for s in result["steps"] if s["step_name"] == "retry")
        assert retry_step_result["status"] == "completed"

        # Continue step failed but continued
        continue_step_result = next(s for s in result["steps"] if s["step_name"] == "continue")
        assert continue_step_result["result"].get("step_error") is True

        # Final step completed with error flag
        final_step_result = next(s for s in result["steps"] if s["step_name"] == "final")
        assert final_step_result["result"]["completed"] is True
        assert final_step_result["result"]["had_error"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
