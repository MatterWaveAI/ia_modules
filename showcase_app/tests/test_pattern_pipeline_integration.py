"""
Test that pattern steps work in actual pipeline execution

This tests the integration between pattern steps and the graph pipeline runner.
"""

import pytest
import json
from pathlib import Path

from ia_modules.pipeline.graph_pipeline_runner import GraphPipelineRunner


class MockAdapter:
    """Mock adapter matching SubprocessAgentAdapter.generate() interface."""

    async def generate(self, prompt: str, model: str = None, temperature: float = 0.7, max_tokens: int = None, **kwargs):
        """Mock generate — returns plain string based on prompt content."""
        if "critique" in prompt.lower() or "score" in prompt.lower():
            return "Score: 8/10\nGood quality, minor improvements possible"
        elif "plan" in prompt.lower() or "step" in prompt.lower():
            return "Step 1: First action\nExpected: Outcome 1\n\nStep 2: Second action\nExpected: Outcome 2"
        elif "valid" in prompt.lower():
            return "VALID: The plan is comprehensive and achievable"
        elif "tool" in prompt.lower() or "calculator" in prompt.lower():
            return "calculator, search"
        else:
            return "Mock response for the given prompt"


@pytest.mark.asyncio
async def test_pipeline_json_structure_validation():
    """Test that pipeline JSON validates correctly"""

    pipeline_config = {
        "name": "test_pipeline",
        "version": "1.0.0",
        "steps": [
            {
                "id": "test_step",
                "name": "Test Step",
                "step_class": "ReflectionStep",
                "module": "backend.pipelines.pattern_steps",
                "config": {
                    "initial_output": "Test",
                    "criteria": {"quality": "High"},
                    "max_iterations": 1
                }
            }
        ],
        "flow": {
            "start_at": "test_step",
            "paths": [
                {
                    "from": "test_step",
                    "to": "end_with_success",
                    "condition": {"type": "always"}
                }
            ]
        }
    }

    GraphPipelineRunner()

    # Should validate without errors
    from ia_modules.pipeline.graph_pipeline_runner import PipelineConfig
    config = PipelineConfig(**pipeline_config)

    assert config.name == "test_pipeline"
    assert len(config.steps) == 1
    assert config.steps[0].id == "test_step"
    assert config.steps[0].step_class == "ReflectionStep"
    assert config.flow.start_at == "test_step"


@pytest.mark.asyncio
async def test_pipeline_json_missing_required_fields():
    """Test that pipeline JSON fails validation with missing fields"""

    from ia_modules.pipeline.graph_pipeline_runner import PipelineConfig

    # Missing 'id' field
    with pytest.raises(Exception):
        PipelineConfig(**{
            "name": "test",
            "steps": [
                {
                    # Missing "id"
                    "name": "Test",
                    "step_class": "TestStep",
                    "module": "test.module",
                    "config": {}
                }
            ],
            "flow": {"start_at": "test", "paths": []}
        })

    # Missing 'flow' field
    with pytest.raises(Exception):
        PipelineConfig(**{
            "name": "test",
            "steps": [
                {
                    "id": "test",
                    "name": "Test",
                    "step_class": "TestStep",
                    "module": "test.module",
                    "config": {}
                }
            ]
            # Missing "flow"
        })


@pytest.mark.asyncio
async def test_agentic_patterns_demo_json_valid():
    """Test that the demo pipeline JSON is valid"""

    # Load the actual demo pipeline
    demo_file = Path(__file__).parent.parent / "backend" / "pipelines" / "agentic_patterns_demo.json"

    if not demo_file.exists():
        pytest.skip("Demo pipeline file not found")

    with open(demo_file, 'r') as f:
        pipeline_config = json.load(f)

    # Should validate
    from ia_modules.pipeline.graph_pipeline_runner import PipelineConfig
    config = PipelineConfig(**pipeline_config)

    assert config.name == "agentic_patterns_demo"
    assert len(config.steps) == 3
    assert config.steps[0].id == "plan_research"
    assert config.steps[0].step_class == "PlanningStep"
    assert config.steps[0].module == "backend.pipelines.pattern_steps"


@pytest.mark.asyncio
async def test_pattern_step_execution_in_pipeline():
    """Test that pattern steps execute correctly in pipeline context"""
    from unittest.mock import patch

    # Patch both possible module paths (test import vs pipeline dynamic import)
    with patch("pipelines.pattern_steps._make_adapter", return_value=MockAdapter()), \
         patch("backend.pipelines.pattern_steps._make_adapter", return_value=MockAdapter()):

        pipeline_config = {
            "name": "reflection_test",
            "version": "1.0.0",
            "steps": [
                {
                    "id": "improve",
                    "name": "Improve Text",
                    "step_class": "ReflectionStep",
                    "module": "backend.pipelines.pattern_steps",
                    "config": {
                        "initial_output": "This is a test",
                        "criteria": {"quality": "Must be high quality"},
                        "max_iterations": 2
                    }
                }
            ],
            "flow": {
                "start_at": "improve",
                "paths": [
                    {
                        "from": "improve",
                        "to": "end_with_success",
                        "condition": {"type": "always"}
                    }
                ]
            }
        }

        runner = GraphPipelineRunner()
        result = await runner.run_pipeline_from_json(pipeline_config, {})

        # Pipeline wraps results — step output is in result['output']
        output = result.get("output", result)
        step_data = output.get("improve", output)
        assert "final_output" in step_data
        assert "final_score" in step_data
        assert step_data["final_score"] >= 6.0


@pytest.mark.asyncio
async def test_multi_pattern_pipeline():
    """Test pipeline with multiple pattern types"""
    from unittest.mock import patch

    with patch("pipelines.pattern_steps._make_adapter", return_value=MockAdapter()), \
         patch("backend.pipelines.pattern_steps._make_adapter", return_value=MockAdapter()):

        pipeline_config = {
            "name": "multi_pattern_test",
            "version": "1.0.0",
            "steps": [
                {
                    "id": "plan",
                    "name": "Plan",
                    "step_class": "PlanningStep",
                    "module": "backend.pipelines.pattern_steps",
                    "config": {
                        "goal": "Test goal",
                        "constraints": []
                    }
                },
                {
                    "id": "reflect",
                    "name": "Reflect",
                    "step_class": "ReflectionStep",
                    "module": "backend.pipelines.pattern_steps",
                    "config": {
                        "initial_output": "Test output",
                        "criteria": {"quality": "High"},
                        "max_iterations": 1
                    }
                }
            ],
            "flow": {
                "start_at": "plan",
                "paths": [
                    {
                        "from": "plan",
                        "to": "reflect",
                        "condition": {"type": "always"}
                    },
                    {
                        "from": "reflect",
                        "to": "end_with_success",
                        "condition": {"type": "always"}
                    }
                ]
            }
        }

        runner = GraphPipelineRunner()
        result = await runner.run_pipeline_from_json(pipeline_config, {})

        # Pipeline wraps results — check output contains both step results
        output = result.get("output", result)
        assert "plan" in output or "goal" in output  # PlanningStep outputs 'plan' key
        reflect_data = output.get("reflect", output)
        assert "final_output" in reflect_data


@pytest.mark.asyncio
async def test_pipeline_json_field_names():
    """Test that correct field names are used (id, step_class, module)"""

    from ia_modules.pipeline.graph_pipeline_runner import PipelineConfig

    # Correct structure
    config = PipelineConfig(**{
        "name": "test",
        "version": "1.0.0",
        "steps": [
            {
                "id": "my_step",              # ✅ Correct: id
                "name": "My Step",             # ✅ Correct: name
                "step_class": "MyStep",        # ✅ Correct: step_class
                "module": "my.module",         # ✅ Correct: module
                "config": {}
            }
        ],
        "flow": {
            "start_at": "my_step",
            "paths": [
                {
                    "from": "my_step",         # ✅ Correct: from
                    "to": "end_with_success",   # ✅ Correct: to
                    "condition": {"type": "always"}
                }
            ]
        }
    })

    assert config.steps[0].id == "my_step"
    assert config.steps[0].step_class == "MyStep"
    assert config.steps[0].module == "my.module"
    assert config.flow.paths[0].from_step == "my_step"
    assert config.flow.paths[0].to_step == "end_with_success"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--asyncio-mode=auto"])
