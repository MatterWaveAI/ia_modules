"""
Unit tests for core pipeline components
"""

import asyncio

import pytest

from ia_modules.pipeline.core import Step, Pipeline
from ia_modules.pipeline.services import ServiceRegistry


class MockStep(Step):
    """Mock step implementation for testing"""

    async def run(self, data: dict) -> dict:
        return {"test_result": "success", "input_data": data}




def test_step():
    """Test step execution"""
    step = MockStep("test_step", {"param": "value"})

    assert step.name == "test_step"
    assert step.config == {"param": "value"}

    # Test run method
    result = asyncio.run(step.run({"input": "data"}))
    assert result["test_result"] == "success"


def test_pipeline_creation():
    """Test pipeline creation"""
    steps = [MockStep("step1", {}), MockStep("step2", {})]
    flow = {
        "start_at": "step1",
        "paths": [
            {"from": "step1", "to": "step2", "condition": {"type": "always"}},
            {"from": "step2", "to": "end_with_success", "condition": {"type": "always"}}
        ]
    }
    services = ServiceRegistry()
    pipeline = Pipeline("test_pipeline", steps, flow, services)

    assert len(pipeline.steps) == 2
    assert pipeline.steps[0].name == "step1"
    assert pipeline.steps[1].name == "step2"




if __name__ == "__main__":
    pytest.main([__file__, "-v"])
