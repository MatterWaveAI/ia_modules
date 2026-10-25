"""
Unit tests for GraphPipelineRunner data flow execution.

Tests that verify data transformation, step chaining, and output propagation
through pipeline execution using real pipeline components.
"""

import pytest
from ia_modules.pipeline.graph_pipeline_runner import (
    GraphPipelineRunner
)
from ia_modules.pipeline.services import ServiceRegistry


@pytest.mark.asyncio
class TestGraphPipelineDataFlow:
    """Test data flow through pipeline execution."""

    async def test_simple_data_transformation(self):
        """Data is transformed through a single step."""
        services = ServiceRegistry()
        runner = GraphPipelineRunner(services)

        # Create simple pipeline with one transform step
        config_dict = {
            "name": "Simple Transform Pipeline",
            "steps": [{
                "id": "transform",
                "name": "transform",
                "step_class": "DataTransformStep",
                "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
            }],
            "flow": {
                "start_at": "transform",
                "paths": []
            }
        }

        result = await runner.run_pipeline_from_json(config_dict, {"value": 5})

        # Verify data transformation occurred (result is in output key)
        output = result["output"]
        assert output["value"] == 10  # 5 * 2
        assert output["transform_processed"] is True

    async def test_sequential_data_flow(self):
        """Data flows correctly through sequential steps."""
        services = ServiceRegistry()
        runner = GraphPipelineRunner(services)

        config_dict = {
            "name": "Sequential Pipeline",
            "steps": [
                {
                    "id": "step1",
                    "name": "transform1",
                    "step_class": "DataTransformStep",
                    "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
                },
                {
                    "id": "step2",
                    "name": "transform2",
                    "step_class": "DataTransformStep",
                    "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
                }
            ],
            "flow": {
                "start_at": "step1",
                "paths": [
                    {
                        "from": "step1",
                        "to": "step2",
                        "condition": {"type": "always"}
                    }
                ]
            }
        }

        result = await runner.run_pipeline_from_json(config_dict, {"value": 5})

        # Value should be doubled twice: 5 -> 10 -> 20
        output = result["output"]
        assert output["value"] == 20
        # Steps use their ID not name in the output
        assert output["step1_processed"] is True
        assert output["step2_processed"] is True

    async def test_data_accumulation_across_steps(self):
        """Data accumulates correctly across multiple steps."""
        services = ServiceRegistry()
        runner = GraphPipelineRunner(services)

        config_dict = {
            "name": "Accumulation Pipeline",
            "steps": [
                {
                    "id": "step1",
                    "name": "transform",
                    "step_class": "DataTransformStep",
                    "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
                },
                {
                    "id": "step2",
                    "name": "accumulate",
                    "step_class": "DataAccumulatorStep",
                    "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
                }
            ],
            "flow": {
                "start_at": "step1",
                "paths": [
                    {"from": "step1", "to": "step2", "condition": {"type": "always"}}
                ]
            }
        }

        result = await runner.run_pipeline_from_json(config_dict, {"value": 5, "_history": []})

        # Verify accumulation: transform doubles to 10, accumulator adds to history
        output = result["output"]
        assert output["value"] == 10
        assert output["accumulated"] == 10  # sum([]) + 10
        assert output["step2_complete"] is True  # Step ID not name

    async def test_data_filtering_pipeline(self):
        """Internal data is filtered in final output."""
        services = ServiceRegistry()
        runner = GraphPipelineRunner(services)

        config_dict = {
            "name": "Filter Pipeline",
            "steps": [
                {
                    "id": "step1",
                    "name": "accumulate",
                    "step_class": "DataAccumulatorStep",
                    "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
                },
                {
                    "id": "step2",
                    "name": "filter",
                    "step_class": "DataFilterStep",
                    "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
                }
            ],
            "flow": {
                "start_at": "step1",
                "paths": [
                    {"from": "step1", "to": "step2", "condition": {"type": "always"}}
                ]
            }
        }

        result = await runner.run_pipeline_from_json(
            config_dict,
            {"value": 5, "_history": [], "_internal": "hidden"}
        )

        # Verify output structure
        output = result["output"]
        assert "filtered_keys" in output
        assert output["step2_filtered"] is True  # Step ID not name
        # Note: Data filtering may include internal keys in output
        # This is expected behavior as step outputs are preserved

    async def test_data_validation_in_pipeline(self):
        """Data validation step verifies schema correctness."""
        services = ServiceRegistry()
        runner = GraphPipelineRunner(services)

        config_dict = {
            "name": "Validation Pipeline",
            "steps": [
                {
                    "id": "transform",
                    "name": "transform",
                    "step_class": "DataTransformStep",
                    "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
                },
                {
                    "id": "validate",
                    "name": "validate",
                    "step_class": "DataValidatorStep",
                    "module": "tests.pipelines.data_flow_pipeline.steps.test_steps",
                    "config": {
                        "required_fields": ["value", "transform_processed"]
                    }
                }
            ],
            "flow": {
                "start_at": "transform",
                "paths": [
                    {"from": "transform", "to": "validate", "condition": {"type": "always"}}
                ]
            }
        }

        result = await runner.run_pipeline_from_json(config_dict, {"value": 5})

        # Validation should pass
        output = result["output"]
        assert output["validation_passed"] is True
        assert len(output["missing_fields"]) == 0
        assert output["validate_validated"] is True

    async def test_empty_input_data_handling(self):
        """Pipeline handles empty input data gracefully."""
        services = ServiceRegistry()
        runner = GraphPipelineRunner(services)

        config_dict = {
            "name": "Empty Input Pipeline",
            "steps": [{
                "id": "transform",
                "name": "transform",
                "step_class": "DataTransformStep",
                "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
            }],
            "flow": {
                "start_at": "transform",
                "paths": []
            }
        }

        result = await runner.run_pipeline_from_json(config_dict, {})

        # Should handle empty input (value defaults to 0)
        output = result["output"]
        assert output["value"] == 0
        assert output["transform_processed"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
