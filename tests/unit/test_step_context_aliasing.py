"""
A step that returns the dict it was given (the guardrail steps do) must not
end up stored inside itself: the pipeline hands each step a copy of the
shared context, and merges what comes back.
"""
import json

from ia_modules.pipeline.core import ExecutionContext, Pipeline, Step
from ia_modules.pipeline.services import ServiceRegistry


class _Passthrough(Step):
    async def run(self, data):
        data["touched_by"] = data.get("touched_by", []) + [self.name]
        return data


async def test_step_returning_its_input_does_not_alias_the_context():
    pipeline = Pipeline(
        name="p",
        steps=[_Passthrough("a", {}), _Passthrough("b", {})],
        flow={"start_at": "a", "paths": [{"from": "a", "to": "b"}, {"from": "b", "to": "end_with_success"}]},
        services=ServiceRegistry(),
        enable_telemetry=False,
    )

    result = await pipeline.run({"user_input": "hi"}, ExecutionContext(execution_id="e1", pipeline_id="p"))

    json.dumps(result, default=str)  # a cycle would raise ValueError
    output = result["output"]
    assert output["touched_by"] == ["a", "b"], "each step saw the previous step's changes"
    assert output["a"] is not output and output["b"] is not output
    assert output["a"]["touched_by"] == ["a"]
