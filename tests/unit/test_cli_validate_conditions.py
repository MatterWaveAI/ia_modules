"""
The validator only trusts the condition types the runner evaluates: 'always'
and 'expression', the latter with a source, one of six operators and a value.
"""
from ia_modules.cli.validate import validate_pipeline


def _pipeline(condition):
    return {
        "name": "t",
        "steps": [
            {"id": "a", "name": "A", "module": "ia_modules.pipeline.core", "step_class": "Step"},
            {"id": "b", "name": "B", "module": "ia_modules.pipeline.core", "step_class": "Step"},
        ],
        "flow": {"start_at": "a", "paths": [
            {"from": "a", "to": "b", "condition": condition},
            {"from": "b", "to": "end_with_success"},
        ]},
    }


def test_expression_condition_is_accepted():
    result = validate_pipeline(_pipeline(
        {"type": "expression", "config": {"source": "a.score", "operator": "greater_than", "value": 0.5}}
    ))
    assert result.is_valid
    assert not result.warnings


def test_types_the_runner_does_not_evaluate_warn():
    result = validate_pipeline(_pipeline({"type": "field_equals", "config": {"field": "x", "value": 1}}))
    assert result.is_valid
    assert any("unknown condition type 'field_equals'" in w and "never be taken" in w for w in result.warnings)


def test_expression_config_is_checked():
    result = validate_pipeline(_pipeline({"type": "expression", "config": {"operator": "between", "value": 1}}))
    assert not result.is_valid
    assert any("missing 'source'" in e for e in result.errors)
    assert any("unknown expression operator 'between'" in e for e in result.errors)

    result = validate_pipeline(_pipeline({"type": "expression"}))
    assert any("needs a 'config' object" in e for e in result.errors)
