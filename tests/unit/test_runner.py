"""Tests for pipeline runner module"""

import pytest
from ia_modules.pipeline.runner import load_step_class, create_step_from_json, create_pipeline_from_json, run_pipeline_from_json
from ia_modules.pipeline.core import Step
from ia_modules.pipeline.services import ServiceRegistry


class DummyStep(Step):
    """Test step class"""

    def execute(self, input_data):
        return {"result": "success", "value": self.config.get("value", 42)}


def test_load_step_class_success():
    """Test loading a step class successfully"""
    step_class = load_step_class('ia_modules.pipeline.core', 'Step')
    assert step_class == Step


def test_load_step_class_import_error():
    """Test load_step_class with non-existent module"""
    with pytest.raises(ImportError) as exc_info:
        load_step_class('non.existent.module', 'SomeClass')
    assert "Cannot import module" in str(exc_info.value)


def test_load_step_class_attribute_error():
    """Test load_step_class with non-existent class"""
    with pytest.raises(AttributeError) as exc_info:
        load_step_class('ia_modules.pipeline.core', 'NonExistentClass')
    assert "has no class" in str(exc_info.value)


def test_create_step_from_json_basic():
    """Test creating step from JSON without template resolution"""
    step_def = {
        'id': 'test_step',
        'module': 'tests.unit.test_runner',
        'class': 'DummyStep',
        'config': {'value': 100}
    }
    step = create_step_from_json(step_def)
    assert step.name == 'test_step'
    assert step.config['value'] == 100


def test_create_step_from_json_with_context():
    """Test creating step with template parameter resolution"""
    step_def = {
        'id': 'test_step',
        'module': 'tests.unit.test_runner',
        'step_class': 'DummyStep',
        'config': {'value': '{{parameters.test_value}}'}
    }
    context = {'parameters': {'test_value': 999}}
    step = create_step_from_json(step_def, context)
    assert step.config['value'] == 999  # Whole-value templates preserve type


def test_create_pipeline_from_json_basic():
    """Test creating pipeline from JSON config"""
    config = {
        'name': 'test_pipeline',
        'steps': [{'id': 'step1', 'module': 'tests.unit.test_runner', 'class': 'DummyStep', 'config': {}}]
    }
    services = ServiceRegistry()
    pipeline = create_pipeline_from_json(config, services=services)
    assert pipeline.name == 'test_pipeline'
    assert len(pipeline.steps) == 1


def test_create_pipeline_from_json_with_flow():
    """Test creating pipeline with graph flow configuration"""
    config = {
        'name': 'test_pipeline',
        'steps': [
            {'id': 'step1', 'module': 'tests.unit.test_runner', 'class': 'DummyStep', 'config': {}},
            {'id': 'step2', 'module': 'tests.unit.test_runner', 'class': 'DummyStep', 'config': {}}
        ],
        'flow': {'start': 'step1', 'routes': [{'from': 'step1', 'to': 'step2'}]}
    }
    services = ServiceRegistry()
    pipeline = create_pipeline_from_json(config, services=services)
    assert len(pipeline.steps) == 2


@pytest.mark.asyncio
async def test_run_pipeline_from_json_file_not_found():
    """Test run_pipeline_from_json with non-existent file"""
    with pytest.raises(FileNotFoundError):
        await run_pipeline_from_json('non_existent_pipeline.json')
