"""
Tests that validate pipeline input/output contracts.

For every pipeline.json that declares inputs/outputs on steps, verify:
1. Source references point to steps that actually exist
2. Referenced output fields are declared on the source step
3. Parameter references match declared pipeline parameters
4. All required fields have valid sources
"""

import json
import re
from pathlib import Path

import pytest

PIPELINES_DIR = Path(__file__).parent.parent / "pipelines"

# Regex to parse source references like {steps.step1.output.topic} or {parameters.topic}
SOURCE_PATTERN = re.compile(
    r"^\{(?:steps\.(?P<step_id>[^.]+)\.output\.(?P<field>[^}]+)"
    r"|parameters\.(?P<param>[^}]+))\}$"
)


def discover_pipelines():
    """Find all pipeline.json files."""
    pipelines = []
    for pipeline_json in sorted(PIPELINES_DIR.glob("*/pipeline.json")):
        pipelines.append(pipeline_json)
    return pipelines


def load_pipeline(path):
    """Load and return parsed pipeline config."""
    with open(path) as f:
        return json.load(f)


def get_step_output_names(step):
    """Extract declared output field names from a step."""
    outputs = step.get("outputs", [])
    if isinstance(outputs, list):
        return {
            (o["name"] if isinstance(o, dict) else o)
            for o in outputs
            if o
        }
    if isinstance(outputs, dict):
        return set(outputs.keys())
    return set()


def get_step_input_entries(step):
    """Extract input entries from a step (list of dicts with name/source)."""
    inputs = step.get("inputs", [])
    if isinstance(inputs, list):
        return [i for i in inputs if isinstance(i, dict) and "name" in i]
    if isinstance(inputs, dict):
        return [{"name": k, "source": v} for k, v in inputs.items()]
    return []


def get_parameter_names(config):
    """Extract declared parameter names from pipeline config."""
    params = config.get("parameters", [])
    if isinstance(params, list):
        return {p["name"] for p in params if isinstance(p, dict) and "name" in p}
    if isinstance(params, dict):
        return set(params.keys())
    return set()


# ── Fixtures ──

PIPELINE_PATHS = discover_pipelines()
PIPELINE_IDS = [p.parent.name for p in PIPELINE_PATHS]


@pytest.fixture(params=PIPELINE_PATHS, ids=PIPELINE_IDS)
def pipeline_config(request):
    """Parametrized fixture: yields (dir_name, config) for each pipeline."""
    path = request.param
    return path.parent.name, load_pipeline(path)


# ── Tests ──


class TestPipelineStructure:
    """Basic structural validation of pipeline.json files."""

    def test_has_steps(self, pipeline_config):
        name, config = pipeline_config
        steps = config.get("steps", [])
        assert len(steps) > 0, f"{name}: pipeline has no steps"

    def test_has_flow(self, pipeline_config):
        name, config = pipeline_config
        flow = config.get("flow", {})
        assert "start_at" in flow, f"{name}: flow missing start_at"
        assert "paths" in flow, f"{name}: flow missing paths"

    def test_start_at_references_valid_step(self, pipeline_config):
        name, config = pipeline_config
        step_ids = {s["id"] for s in config.get("steps", [])}
        start = config.get("flow", {}).get("start_at", "")
        assert start in step_ids, (
            f"{name}: start_at '{start}' not in step IDs: {step_ids}"
        )

    def test_flow_paths_reference_valid_steps(self, pipeline_config):
        name, config = pipeline_config
        step_ids = {s["id"] for s in config.get("steps", [])}
        paths = config.get("flow", {}).get("paths", [])

        for i, path in enumerate(paths):
            from_step = path.get("from_step") or path.get("from")
            to_step = path.get("to_step") or path.get("to")
            assert from_step in step_ids, (
                f"{name}: path[{i}] from '{from_step}' not in step IDs"
            )
            assert to_step in step_ids, (
                f"{name}: path[{i}] to '{to_step}' not in step IDs"
            )

    def test_unique_step_ids(self, pipeline_config):
        name, config = pipeline_config
        step_ids = [s["id"] for s in config.get("steps", [])]
        assert len(step_ids) == len(set(step_ids)), (
            f"{name}: duplicate step IDs found"
        )


class TestInputOutputContracts:
    """Validate that input source references point to real outputs."""

    def test_step_source_references_valid_step(self, pipeline_config):
        """Every {steps.X.output.Y} reference must point to a step that exists."""
        name, config = pipeline_config
        step_ids = {s["id"] for s in config.get("steps", [])}

        for step in config.get("steps", []):
            for inp in get_step_input_entries(step):
                source = inp.get("source", "")
                if not source:
                    continue
                match = SOURCE_PATTERN.match(source)
                if not match:
                    continue
                ref_step = match.group("step_id")
                if ref_step:
                    assert ref_step in step_ids, (
                        f"{name}/{step['id']}: input '{inp['name']}' references "
                        f"step '{ref_step}' which doesn't exist. "
                        f"Valid steps: {step_ids}"
                    )

    def test_step_source_references_declared_output(self, pipeline_config):
        """Every {steps.X.output.Y} must reference a field X actually declares as output."""
        name, config = pipeline_config
        steps_by_id = {s["id"]: s for s in config.get("steps", [])}

        for step in config.get("steps", []):
            for inp in get_step_input_entries(step):
                source = inp.get("source", "")
                if not source:
                    continue
                match = SOURCE_PATTERN.match(source)
                if not match:
                    continue
                ref_step_id = match.group("step_id")
                ref_field = match.group("field")
                if not ref_step_id or not ref_field:
                    continue

                ref_step = steps_by_id.get(ref_step_id)
                if not ref_step:
                    continue  # Caught by other test

                declared_outputs = get_step_output_names(ref_step)
                if not declared_outputs:
                    # Step has no declared outputs — skip (may use inferred)
                    continue

                assert ref_field in declared_outputs, (
                    f"{name}/{step['id']}: input '{inp['name']}' references "
                    f"'{ref_step_id}.output.{ref_field}' but {ref_step_id} only "
                    f"declares outputs: {declared_outputs}"
                )

    def test_parameter_references_valid(self, pipeline_config):
        """Every {parameters.X} must reference a declared pipeline parameter."""
        name, config = pipeline_config
        param_names = get_parameter_names(config)
        if not param_names:
            pytest.skip(f"{name}: no parameters declared")

        for step in config.get("steps", []):
            for inp in get_step_input_entries(step):
                source = inp.get("source", "")
                if not source:
                    continue
                match = SOURCE_PATTERN.match(source)
                if not match:
                    continue
                param_ref = match.group("param")
                if not param_ref:
                    continue
                # Handle nested like input_data.task -> check input_data
                top_level = param_ref.split(".")[0]
                assert top_level in param_names, (
                    f"{name}/{step['id']}: input '{inp['name']}' references "
                    f"parameter '{top_level}' which isn't declared. "
                    f"Declared params: {param_names}"
                )

    def test_all_steps_have_inputs_or_outputs(self, pipeline_config):
        """Every step should declare at least inputs or outputs (catches lazy omissions)."""
        name, config = pipeline_config
        _start_at = config.get("flow", {}).get("start_at", "")

        missing = []
        for step in config.get("steps", []):
            inputs = step.get("inputs")
            outputs = step.get("outputs")
            has_inputs = inputs and (
                (isinstance(inputs, list) and len(inputs) > 0)
                or (isinstance(inputs, dict) and len(inputs) > 0)
            )
            has_outputs = outputs and (
                (isinstance(outputs, list) and len(outputs) > 0)
                or (isinstance(outputs, dict) and len(outputs) > 0)
            )
            if not has_inputs and not has_outputs:
                missing.append(step["id"])

        assert len(missing) == 0, (
            f"{name}: steps missing inputs AND outputs: {missing}"
        )


class TestInputOutputCompleteness:
    """Check that every step connected in the flow has matching ports."""

    def test_every_connected_step_has_outputs(self, pipeline_config):
        """Steps that feed into other steps should declare outputs."""
        name, config = pipeline_config
        steps_by_id = {s["id"]: s for s in config.get("steps", [])}
        paths = config.get("flow", {}).get("paths", [])

        missing = []
        for path in paths:
            from_id = path.get("from_step") or path.get("from")
            step = steps_by_id.get(from_id)
            if step and not step.get("outputs"):
                missing.append(from_id)

        # Deduplicate
        missing = list(set(missing))
        assert len(missing) == 0, (
            f"{name}: steps with outgoing edges but no declared outputs: {missing}"
        )

    def test_every_connected_step_has_inputs(self, pipeline_config):
        """Steps that receive data should declare inputs (except start step)."""
        name, config = pipeline_config
        steps_by_id = {s["id"]: s for s in config.get("steps", [])}
        start_at = config.get("flow", {}).get("start_at", "")
        paths = config.get("flow", {}).get("paths", [])

        missing = []
        for path in paths:
            to_id = path.get("to_step") or path.get("to")
            if to_id == start_at:
                continue  # Start step may only take parameters
            step = steps_by_id.get(to_id)
            if step and not step.get("inputs"):
                missing.append(to_id)

        missing = list(set(missing))
        assert len(missing) == 0, (
            f"{name}: steps with incoming edges but no declared inputs: {missing}"
        )
