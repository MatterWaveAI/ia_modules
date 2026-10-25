"""
Unit tests for GraphPipelineRunner advanced features.

Tests enhanced pipeline features, scenario execution, and edge cases.
"""

import pytest
from ia_modules.pipeline.graph_pipeline_runner import (
    GraphPipelineRunner
)
from ia_modules.pipeline.services import ServiceRegistry
from ia_modules.pipeline.core import Step
from typing import Dict, Any


class ConditionalStep(Step):
    """Test step that sets conditional flags for routing"""

    async def run(self, data: Dict[str, Any]) -> Any:
        threshold = self.config.get("threshold", 50)
        value = data.get("value", 0)

        return {
            **data,
            "should_continue": value > threshold,
            "threshold_met": value > threshold,
            f"{self.name}_executed": True
        }


class BranchAStep(Step):
    """Branch A processing"""

    async def run(self, data: Dict[str, Any]) -> Any:
        return {**data, "branch": "A", "branch_a_processed": True}


class BranchBStep(Step):
    """Branch B processing"""

    async def run(self, data: Dict[str, Any]) -> Any:
        return {**data, "branch": "B", "branch_b_processed": True}


class ParallelStep(Step):
    """Step designed for parallel execution"""

    async def run(self, data: Dict[str, Any]) -> Any:
        import asyncio
        # Simulate some processing time
        await asyncio.sleep(0.1)

        step_id = self.name
        return {
            **data,
            f"{step_id}_completed": True,
            f"{step_id}_value": data.get("value", 0) + int(step_id.split("_")[-1])
        }


@pytest.mark.asyncio
class TestGraphPipelineAdvanced:
    """Test advanced features of GraphPipelineRunner."""

    async def test_pipeline_config_validation(self):
        """Pipeline configuration is validated correctly."""
        services = ServiceRegistry()
        runner = GraphPipelineRunner(services)

        # Valid config with real step class
        valid_config = {
            "name": "Test",
            "steps": [
                {
                    "id": "step1",
                    "name": "step1",
                    "step_class": "DataTransformStep",
                    "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
                }
            ],
            "flow": {"start_at": "step1", "paths": []}
        }

        # Should not raise
        result = await runner.run_pipeline_from_json(
            valid_config,
            {"value": 1}
        )
        assert "output" in result

    async def test_invalid_pipeline_config_raises_error(self):
        """Invalid pipeline configuration raises ValueError."""
        services = ServiceRegistry()
        runner = GraphPipelineRunner(services)

        # Missing required field 'name'
        invalid_config = {
            "steps": [
                {"id": "step1", "name": "step1", "step_class": "Step", "module": "test"}
            ],
            "flow": {"start_at": "step1", "paths": []}
        }

        with pytest.raises(ValueError, match="Invalid pipeline configuration"):
            await runner.run_pipeline_from_json(invalid_config, {})

    async def test_conditional_branching(self):
        """Pipeline correctly handles conditional branching."""
        services = ServiceRegistry()
        runner = GraphPipelineRunner(services)

        # Pipeline with conditional logic
        config = {
            "name": "Conditional Branch Pipeline",
            "steps": [
                {
                    "id": "check",
                    "name": "check",
                    "step_class": "ConditionalStep",
                    "module": "tests.unit.test_graph_pipeline_advanced",
                    "config": {"threshold": 50}
                },
                {
                    "id": "branch_a",
                    "name": "branch_a",
                    "step_class": "BranchAStep",
                    "module": "tests.unit.test_graph_pipeline_advanced"
                },
                {
                    "id": "branch_b",
                    "name": "branch_b",
                    "step_class": "BranchBStep",
                    "module": "tests.unit.test_graph_pipeline_advanced"
                }
            ],
            "flow": {
                "start_at": "check",
                "paths": [
                    # Note: GraphPipelineRunner doesn't natively support conditional paths
                    # This tests that it executes the defined paths
                    {"from": "check", "to": "branch_a", "condition": {"type": "always"}}
                ]
            }
        }

        # High value - should set should_continue to True
        result = await runner.run_pipeline_from_json(config, {"value": 100})
        output = result["output"]

        assert output["should_continue"] is True
        assert output["threshold_met"] is True
        assert output["branch"] == "A"

    async def test_execution_stats_tracking(self):
        """Runner tracks execution statistics."""
        services = ServiceRegistry()
        runner = GraphPipelineRunner(services)

        config = {
            "name": "Stats Test",
            "steps": [{
                "id": "step1",
                "name": "step1",
                "step_class": "DataTransformStep",
                "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
            }],
            "flow": {"start_at": "step1", "paths": []}
        }

        await runner.run_pipeline_from_json(config, {"value": 5})

        # Check execution stats were populated
        assert "start_time" in runner.execution_stats
        assert "end_time" in runner.execution_stats
        assert runner.execution_stats["start_time"] is not None
        assert runner.execution_stats["end_time"] is not None

    async def test_pipeline_with_metadata(self):
        """Pipeline configuration with metadata is handled correctly."""
        services = ServiceRegistry()
        runner = GraphPipelineRunner(services)

        config = {
            "name": "Metadata Test",
            "description": "Pipeline with metadata",
            "version": "1.0.0",
            "metadata": {
                "author": "test",
                "tags": ["test", "example"],
                "complexity": "simple"
            },
            "steps": [{
                "id": "step1",
                "name": "step1",
                "step_class": "DataTransformStep",
                "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
            }],
            "flow": {"start_at": "step1", "paths": []}
        }

        result = await runner.run_pipeline_from_json(config, {"value": 5})

        # Pipeline should execute successfully despite metadata
        assert "output" in result
        assert result["output"]["value"] == 10

    async def test_pipeline_with_input_output_schemas(self):
        """Pipeline with input/output schemas is processed."""
        services = ServiceRegistry()
        runner = GraphPipelineRunner(services)

        config = {
            "name": "Schema Test",
            "input_schema": {
                "type": "object",
                "properties": {
                    "value": {"type": "number"}
                }
            },
            "output_schema": {
                "type": "object",
                "properties": {
                    "value": {"type": "number"},
                    "processed": {"type": "boolean"}
                }
            },
            "steps": [{
                "id": "step1",
                "name": "step1",
                "step_class": "DataTransformStep",
                "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
            }],
            "flow": {"start_at": "step1", "paths": []}
        }

        result = await runner.run_pipeline_from_json(config, {"value": 5})

        # Schemas don't affect execution in current implementation
        assert result["output"]["value"] == 10

    async def test_empty_paths_single_step(self):
        """Pipeline with single step and no paths executes correctly."""
        services = ServiceRegistry()
        runner = GraphPipelineRunner(services)

        config = {
            "name": "Single Step",
            "steps": [{
                "id": "only_step",
                "name": "only_step",
                "step_class": "DataTransformStep",
                "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
            }],
            "flow": {
                "start_at": "only_step",
                "paths": []  # No paths - single terminal step
            }
        }

        result = await runner.run_pipeline_from_json(config, {"value": 3})
        assert result["output"]["value"] == 6

    async def test_multiple_paths_from_single_step(self):
        """Step with multiple outgoing paths is handled."""
        services = ServiceRegistry()
        runner = GraphPipelineRunner(services)

        config = {
            "name": "Multiple Paths",
            "steps": [
                {
                    "id": "start",
                    "name": "start",
                    "step_class": "DataTransformStep",
                    "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
                },
                {
                    "id": "branch_a",
                    "name": "branch_a",
                    "step_class": "BranchAStep",
                    "module": "tests.unit.test_graph_pipeline_advanced"
                },
                {
                    "id": "branch_b",
                    "name": "branch_b",
                    "step_class": "BranchBStep",
                    "module": "tests.unit.test_graph_pipeline_advanced"
                }
            ],
            "flow": {
                "start_at": "start",
                "paths": [
                    # Multiple paths from same step
                    {"from": "start", "to": "branch_a", "condition": {"type": "always"}},
                    {"from": "start", "to": "branch_b", "condition": {"type": "always"}}
                ]
            }
        }

        # In current implementation, only first matching path is taken
        result = await runner.run_pipeline_from_json(config, {"value": 5})
        output = result["output"]

        # Should follow first path
        assert "branch" in output

    async def test_pipeline_result_structure(self):
        """Pipeline result has correct structure."""
        services = ServiceRegistry()
        runner = GraphPipelineRunner(services)

        config = {
            "name": "Result Structure Test",
            "steps": [{
                "id": "step1",
                "name": "step1",
                "step_class": "DataTransformStep",
                "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
            }],
            "flow": {"start_at": "step1", "paths": []}
        }

        result = await runner.run_pipeline_from_json(config, {"value": 10})

        # Verify result structure
        assert "input" in result
        assert "steps" in result
        assert "output" in result

        # Input now contains original input plus step results
        assert "value" in result["input"]
        assert isinstance(result["steps"], list)
        assert len(result["steps"]) == 1

        step_result = result["steps"][0]
        assert "step_name" in step_result
        assert "step_index" in step_result
        assert "result" in step_result
        assert "status" in step_result
        assert step_result["status"] == "completed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
