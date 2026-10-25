"""
Integration tests for pipeline runner with real configurations
"""

from unittest.mock import Mock, patch

import pytest

from ia_modules.pipeline.runner import (
    load_step_class,
    create_step_from_json,
    create_pipeline_from_json
)
from ia_modules.pipeline.test_utils import create_test_execution_context
from ia_modules.pipeline.core import Step
from ia_modules.pipeline.services import ServiceRegistry


class IntegrationTestStep(Step):
    """Test step implementation"""

    async def run(self, data: dict) -> dict:
        return {"result": "success", "input_data": data, "step_name": self.name}


@pytest.mark.asyncio
async def test_load_step_class_integration():
    """Test loading step class with real import mocking"""
    # Mock the import to use our test step
    with patch('importlib.import_module') as mock_import:
        mock_module = Mock()
        mock_module.IntegrationTestStep = IntegrationTestStep
        mock_import.return_value = mock_module
        
        loaded_class = load_step_class("test.module", "IntegrationTestStep")
        assert loaded_class == IntegrationTestStep


@pytest.mark.asyncio
async def test_create_step_from_json_integration():
    """Test creating step from JSON with real configuration"""
    step_def = {
        "id": "test_step",
        "step_class": "IntegrationTestStep",
        "module": "test.module",
        "config": {"param1": "value1", "param2": 42}
    }
    
    # Mock the import
    with patch('importlib.import_module') as mock_import:
        mock_module = Mock()
        mock_module.IntegrationTestStep = IntegrationTestStep
        mock_import.return_value = mock_module
        
        context = {"parameters": {}}
        step = create_step_from_json(step_def, context)
        
        assert step.name == "test_step"
        assert step.config == {"param1": "value1", "param2": 42}


@pytest.mark.asyncio
async def test_create_pipeline_from_json_integration():
    """Test creating pipeline from JSON with real configuration"""
    pipeline_config = {
        "name": "Integration Test Pipeline",
        "steps": [
            {
                "id": "step1",
                "step_class": "IntegrationTestStep",
                "module": "test.module",
                "config": {"param": "value"}
            }
        ],
        "flow": {
            "start_at": "step1",
            "paths": []
        }
    }
    
    # Mock the import
    with patch('importlib.import_module') as mock_import:
        mock_module = Mock()
        mock_module.IntegrationTestStep = IntegrationTestStep
        mock_import.return_value = mock_module
        
        services = ServiceRegistry()
        pipeline = create_pipeline_from_json(pipeline_config, services)
        
        assert len(pipeline.steps) == 1
        assert pipeline.steps[0].name == "step1"


@pytest.mark.asyncio
async def test_full_pipeline_integration():
    """Test full pipeline execution with real configuration"""
    # Create a more complex pipeline configuration
    pipeline_config = {
        "name": "Full Integration Test Pipeline",
        "steps": [
            {
                "id": "step1",
                "step_class": "IntegrationTestStep",
                "module": "test.module",
                "config": {"param": "value1"}
            },
            {
                "id": "step2", 
                "step_class": "IntegrationTestStep",
                "module": "test.module",
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

    # Mock the import
    with patch('importlib.import_module') as mock_import:
        mock_module = Mock()
        mock_module.IntegrationTestStep = IntegrationTestStep
        mock_import.return_value = mock_module
        
        services = ServiceRegistry()
        pipeline = create_pipeline_from_json(pipeline_config, services)
        
        # Test execution
        result = await pipeline.run({"input": "test_data"}, create_test_execution_context())
        
        assert result is not None
        assert isinstance(result, dict)
        assert "input" in result
        assert "steps" in result
        assert "output" in result
        assert result["input"]["input"] == "test_data"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
