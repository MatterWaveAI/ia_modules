"""
Integration tests for pipeline functionality
"""

import asyncio

import pytest

from ia_modules.pipeline.core import Step
from ia_modules.pipeline.test_utils import create_test_execution_context
from ia_modules.pipeline.runner import create_pipeline_from_json
from ia_modules.pipeline.services import ServiceRegistry


class IntegrationTestStep(Step):
    """Test step implementation"""

    async def run(self, data: dict) -> dict:
        return {"processed": True, "data": data}


@pytest.mark.asyncio
async def test_pipeline_integration():
    """Test full pipeline integration"""
    # Create a simple pipeline configuration
    pipeline_config = {
        "name": "Integration Test Pipeline",
        "steps": [
            {
                "id": "step1",
                "step_class": "IntegrationTestStep",
                "module": "tests.integration.test_pipeline_integration",
                "config": {"param": "value"}
            }
        ],
        "flow": {
            "start_at": "step1",
            "paths": [
                {
                    "from": "step1",
                    "to": "end_with_success",
                    "condition": {"type": "always"}
                }
            ]
        }
    }

    # Create services
    services = ServiceRegistry()
    
    # Create and run pipeline
    pipeline = create_pipeline_from_json(pipeline_config, services)
    result = await pipeline.run({"input": "test_data"}, create_test_execution_context())
    
    assert result is not None
    assert isinstance(result, dict)
    assert "input" in result
    assert "steps" in result
    assert "output" in result
    assert result["input"]["input"] == "test_data"


@pytest.mark.asyncio
async def test_complex_pipeline_integration():
    """Test complex pipeline with multiple steps"""
    # Create a more complex pipeline configuration
    pipeline_config = {
        "name": "Complex Integration Test Pipeline",
        "steps": [
            {
                "id": "step1",
                "step_class": "IntegrationTestStep",
                "module": "tests.integration.test_pipeline_integration",
                "config": {"param": "value1"}
            },
            {
                "id": "step2", 
                "step_class": "IntegrationTestStep",
                "module": "tests.integration.test_pipeline_integration",
                "config": {"param": "value2"}
            }
        ],
        "flow": {
            "start_at": "step1",
            "paths": [
                {
                    "from": "step1",
                    "to": "step2",
                    "condition": {"type": "always"}
                },
                {
                    "from": "step2",
                    "to": "end_with_success",
                    "condition": {"type": "always"}
                }
            ]
        }
    }

    # Create services
    services = ServiceRegistry()
    
    # Create and run pipeline
    pipeline = create_pipeline_from_json(pipeline_config, services)
    result = await pipeline.run({"input": "test_data"}, create_test_execution_context())
    
    assert result is not None
    assert isinstance(result, dict)
    assert "input" in result
    assert "steps" in result
    assert "output" in result
    assert result["input"]["input"] == "test_data"


if __name__ == "__main__":
    # Run tests manually if needed
    asyncio.run(test_pipeline_integration())
    asyncio.run(test_complex_pipeline_integration())
