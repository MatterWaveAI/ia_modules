"""
Pipeline parameters: schema defaults fill in, required ones are checked before
anything runs, and a template naming a missing parameter is an error rather
than a literal string that fails later with a bare TypeError.
"""
import json
from pathlib import Path

import pytest

from ia_modules.pipeline.core import ExecutionContext, TemplateParameterResolver
from ia_modules.pipeline.graph_pipeline_runner import GraphPipelineRunner
from ia_modules.pipeline.runner import create_pipeline_from_json
from ia_modules.pipeline.services import ServiceRegistry


def _config():
    return {
        "name": "p",
        "parameters": [
            {"name": "threshold", "schema": {"type": "number"}, "required": True},
            {"name": "label", "schema": {"type": "string"}, "default": "untitled"},
        ],
        "steps": [{
            "id": "a", "name": "A", "module": "ia_modules.pipeline.core", "step_class": "Step",
            "config": {"limit": "{{ parameters.threshold }}", "title": "Run: {{ parameters.label }}"},
        }],
        "flow": {"start_at": "a", "paths": [{"from": "a", "to": "end_with_success"}]},
    }


def test_missing_required_parameter_is_reported_up_front():
    with pytest.raises(ValueError, match="requires parameters it was not given: threshold"):
        create_pipeline_from_json(_config(), ServiceRegistry(), input_data={})


def test_defaults_fill_in_and_values_keep_their_type():
    pipeline = create_pipeline_from_json(_config(), ServiceRegistry(), input_data={"threshold": 0.7})

    step = pipeline.steps[0]
    assert step.config["limit"] == 0.7
    assert step.config["title"] == "Run: untitled"


def test_unresolvable_template_is_an_error():
    resolve = TemplateParameterResolver.resolve_parameters

    with pytest.raises(ValueError, match="parameter 'missing' was not provided"):
        resolve({"x": "{{ parameters.missing }}"}, {"parameters": {}})
    with pytest.raises(ValueError, match="parameter 'missing' was not provided"):
        resolve({"x": "hi {{ parameters.missing }}"}, {"parameters": {}})

    # Other template namespaces are someone else's to resolve
    assert resolve({"x": "{{ steps.a.output }}"}, {"parameters": {}}) == {"x": "{{ steps.a.output }}"}


async def test_runner_reports_missing_parameters_before_running():
    """The example pipeline declares threshold and test_data as required"""
    pipeline_file = Path(__file__).parent.parent / "pipelines" / "conditional_pipeline" / "pipeline.json"
    config = json.loads(pipeline_file.read_text(encoding="utf-8"))

    with pytest.raises(ValueError, match="requires parameters it was not given: threshold, test_data"):
        await GraphPipelineRunner().run_pipeline_from_json(config, {"data": "not the declared inputs"})


def test_building_without_inputs_defers_the_check():
    """A pipeline built now and run with its inputs later must still build"""
    pipeline = create_pipeline_from_json(_config(), ServiceRegistry())

    step = pipeline.steps[0]
    assert step.config["limit"] == "{{ parameters.threshold }}"  # unknown until run time
    assert step.config["title"] == "Run: untitled"  # defaults still apply


async def test_build_then_run_with_inputs():
    pipeline_file = Path(__file__).parent.parent / "pipelines" / "parallel_pipeline" / "pipeline.json"
    config = json.loads(pipeline_file.read_text(encoding="utf-8"))

    pipeline = create_pipeline_from_json(config, ServiceRegistry())
    result = await pipeline.run(
        {"loaded_data": [{"value": n} for n in range(6)]},
        ExecutionContext(execution_id="e1", pipeline_id="parallel"),
    )

    assert result["output"]["total_records_processed"] == 6

