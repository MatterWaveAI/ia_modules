"""
Integration tests for graph pipeline runner with real scenarios
"""


import pytest

from ia_modules.pipeline.graph_pipeline_runner import GraphPipelineRunner, PipelineConfig
from ia_modules.pipeline.services import ServiceRegistry


@pytest.mark.asyncio
async def test_graph_pipeline_runner_creation_integration():
    """Test graph pipeline runner creation with real services"""
    services = ServiceRegistry()
    runner = GraphPipelineRunner(services)
    
    assert runner is not None
    assert runner.services == services


@pytest.mark.asyncio
async def test_pipeline_config_validation_integration():
    """Test pipeline configuration validation with real data"""
    # Test valid config
    config_dict = {
        "name": "Integration Test Pipeline",
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
    
    assert config.name == "Integration Test Pipeline"
    assert len(config.steps) == 1


@pytest.mark.asyncio
async def test_pipeline_config_validation_with_flow_integration():
    """Test pipeline configuration validation with flow paths"""
    # Test valid config with flow paths
    config_dict = {
        "name": "Flow Integration Test Pipeline",
        "steps": [
            {
                "id": "step1",
                "name": "Step 1",
                "step_class": "TestStep",
                "module": "test.module"
            },
            {
                "id": "step2",
                "name": "Step 2", 
                "step_class": "TestStep",
                "module": "test.module"
            }
        ],
        "flow": {
            "start_at": "step1",
            "paths": [
                {
                    "from_step": "step1",
                    "to_step": "step2",
                    "condition": {"type": "always"}
                },
                {
                    "from_step": "step2",
                    "to_step": "end_with_success",
                    "condition": {"type": "always"}
                }
            ]
        }
    }
    
    # This should not raise an exception
    config = PipelineConfig(**config_dict)
    
    assert config.name == "Flow Integration Test Pipeline"
    assert len(config.steps) == 2
    assert len(config.flow.paths) == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
