"""
Unit tests for graph pipeline runner
"""


import pytest

from ia_modules.pipeline.core import Step, ExecutionContext
from ia_modules.pipeline.graph_pipeline_runner import GraphPipelineRunner, PipelineConfig
from ia_modules.pipeline.services import ServiceRegistry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
class EchoStep(Step):
    """Simple step that echoes input with a prefix."""

    async def run(self, data):
        prefix = self.config.get("prefix", self.name)
        return {"result": f"[{prefix}] {data.get('message', '')}"}


class UpperStep(Step):
    """Step that uppercases the previous result."""

    async def run(self, data):
        prev = data.get("result", "")
        return {"result": prev.upper()}


# ---------------------------------------------------------------------------
# Existing tests
# ---------------------------------------------------------------------------
def test_graph_pipeline_runner_creation():
    """Test graph pipeline runner creation"""
    services = ServiceRegistry()
    runner = GraphPipelineRunner(services)

    assert runner is not None
    assert runner.services == services


def test_pipeline_config_validation():
    """Test pipeline configuration validation"""
    # Test valid config
    config_dict = {
        "name": "Test Pipeline",
        "steps": [
            {
                "id": "step1",
                "name": "Step 1",
                "step_class": "TestStep",
                "module": "test.module"
            }
        ],
        "flow": {
            "start_at": "step1",
            "paths": []
        }
    }

    # This should not raise an exception
    config = PipelineConfig(**config_dict)

    assert config.name == "Test Pipeline"
    assert len(config.steps) == 1


# ---------------------------------------------------------------------------
# run_pipeline tests
# ---------------------------------------------------------------------------
@pytest.mark.asyncio
async def test_run_pipeline_single_step():
    """run_pipeline executes a single pre-built step."""
    runner = GraphPipelineRunner()

    steps = [EchoStep("echo", {"prefix": "hello"})]
    flow = {"start_at": "echo", "paths": []}

    result = await runner.run_pipeline(
        name="single",
        steps=steps,
        flow=flow,
        input_data={"message": "world"},
    )

    assert result["output"]["result"] == "[hello] world"
    assert runner.execution_stats["steps_executed"] == 1


@pytest.mark.asyncio
async def test_run_pipeline_linear_chain():
    """run_pipeline chains two steps: echo → upper."""
    runner = GraphPipelineRunner()

    steps = [
        EchoStep("echo", {"prefix": "greet"}),
        UpperStep("upper", {}),
    ]
    flow = {
        "start_at": "echo",
        "paths": [
            {"from": "echo", "to": "upper", "condition": {"type": "always"}},
        ],
    }

    result = await runner.run_pipeline(
        name="chain",
        steps=steps,
        flow=flow,
        input_data={"message": "hi"},
    )

    assert result["output"]["result"] == "[GREET] HI"
    assert runner.execution_stats["steps_executed"] == 2


@pytest.mark.asyncio
async def test_run_pipeline_with_execution_context():
    """run_pipeline accepts an ExecutionContext."""
    runner = GraphPipelineRunner()

    steps = [EchoStep("s1", {"prefix": "ctx"})]
    flow = {"start_at": "s1", "paths": []}
    ctx = ExecutionContext(execution_id="test-123", pipeline_id="ctx-pipe")

    result = await runner.run_pipeline(
        name="ctx-pipe",
        steps=steps,
        flow=flow,
        input_data={"message": "ok"},
        execution_context=ctx,
    )

    assert result["output"]["result"] == "[ctx] ok"


@pytest.mark.asyncio
async def test_run_pipeline_auto_creates_context():
    """run_pipeline creates an ExecutionContext when none is provided."""
    runner = GraphPipelineRunner()

    steps = [EchoStep("auto", {})]
    flow = {"start_at": "auto", "paths": []}

    result = await runner.run_pipeline(
        name="auto-ctx",
        steps=steps,
        flow=flow,
        input_data={"message": "test"},
    )

    assert result["output"]["result"] == "[auto] test"


@pytest.mark.asyncio
async def test_run_pipeline_step_failure_propagates():
    """run_pipeline propagates step errors."""

    class FailStep(Step):
        async def run(self, data):
            raise RuntimeError("boom")

    runner = GraphPipelineRunner()
    steps = [FailStep("fail", {})]
    flow = {"start_at": "fail", "paths": []}

    with pytest.raises(Exception):
        await runner.run_pipeline(
            name="fail-pipe",
            steps=steps,
            flow=flow,
            input_data={},
        )


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
