"""
Flow paths may be spelled from/to or from_step/to_step; every consumer accepts both.
"""
import pytest

from ia_modules.cli.validate import validate_pipeline
from ia_modules.pipeline.core import Pipeline, Step
from ia_modules.pipeline.flow import normalize_flow, path_endpoints
from ia_modules.pipeline.loop_detector import LoopDetector
from ia_modules.pipeline.services import ServiceRegistry


def test_normalize_flow_rewrites_from_step_paths():
    flow = {"start_at": "a", "paths": [
        {"from_step": "a", "to_step": "b", "condition": {"type": "always"}},
        {"from": "b", "to": "end_with_success"},
    ]}

    normalized = normalize_flow(flow)

    assert normalized["paths"] == [
        {"from": "a", "to": "b", "condition": {"type": "always"}},
        {"from": "b", "to": "end_with_success"},
    ]
    assert normalized["start_at"] == "a"
    # The caller's flow is left alone
    assert flow["paths"][0] == {"from_step": "a", "to_step": "b", "condition": {"type": "always"}}


def test_normalize_flow_returns_canonical_flow_unchanged():
    flow = {"paths": [{"from": "a", "to": "b"}]}
    assert normalize_flow(flow) is flow
    assert normalize_flow(None) is None
    assert normalize_flow({"transitions": []}) == {"transitions": []}


def test_path_endpoints_prefers_canonical_keys():
    assert path_endpoints({"from_step": "a", "to_step": "b"}) == ("a", "b")
    assert path_endpoints({"from": "a", "to": "b", "from_step": "x"}) == ("a", "b")
    assert path_endpoints({}) == (None, None)


def test_loop_detector_accepts_from_step_paths():
    detector = LoopDetector({"paths": [
        {"from_step": "a", "to_step": "b"},
        {"from_step": "b", "to_step": "a", "condition": {"type": "expression", "expression": "x < 3"}},
    ]})

    assert detector.transitions[0] == {"from": "a", "to": "b"}
    assert len(detector.detect_loops()) == 1


class _Noop(Step):
    async def run(self, data):
        return {}


def test_pipeline_normalizes_its_flow():
    pipeline = Pipeline(
        name="p",
        steps=[_Noop("a", {}), _Noop("b", {})],
        flow={"start_at": "a", "paths": [{"from_step": "a", "to_step": "b"}]},
        services=ServiceRegistry(),
        enable_telemetry=False,
    )
    assert pipeline.flow["paths"] == [{"from": "a", "to": "b"}]


@pytest.mark.parametrize("source, target", [("from", "to"), ("from_step", "to_step")])
def test_validator_accepts_both_spellings(source, target):
    pipeline = {
        "name": "t",
        "steps": [
            {"name": "step1", "module": "ia_modules.pipeline.core", "class": "Step"},
            {"name": "step2", "module": "ia_modules.pipeline.core", "class": "Step"},
        ],
        "flow": {"start_at": "step1", "paths": [
            {source: "step1", target: "step2"},
            {source: "step2", target: "end_with_success"},
        ]},
    }

    result = validate_pipeline(pipeline)
    assert result.is_valid is True
    assert not [w for w in result.warnings if "Unreachable" in w]

    pipeline["flow"]["paths"][0][target] = "missing"
    result = validate_pipeline(pipeline)
    assert result.is_valid is False
    assert any(f"'{target}' 'missing' is not defined" in e for e in result.errors)
