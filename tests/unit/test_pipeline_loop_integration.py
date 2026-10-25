"""
Integration tests for Pipeline loop detection
"""

import pytest
from ia_modules.pipeline.core import Pipeline, Step
from ia_modules.pipeline.test_utils import create_test_execution_context
from ia_modules.pipeline.services import ServiceRegistry


class DummyStep(Step):
    """Simple step for testing"""
    async def run(self, data):
        return {'result': 'ok', **data}


class TestPipelineLoopIntegration:
    """Test Pipeline class integration with loop detection"""

    def test_pipeline_without_flow(self):
        """Pipeline without flow should not have loops"""
        flow = {'start_at': 'step1'}
        steps = [DummyStep('step1', {})]
        pipeline = Pipeline('test', steps, flow, ServiceRegistry())

        assert pipeline.has_loops() is False
        assert pipeline.get_loops() == []
        assert pipeline.loop_detector is None
        assert pipeline.loop_executor is None

    def test_pipeline_with_sequential_transitions(self):
        """Pipeline with sequential transitions (no cycles) should not have loops"""
        flow = {
            'start_at': 'step1',
            'paths': [
                {'from': 'step1', 'to': 'step2'},
                {'from': 'step2', 'to': 'end'}
            ]
        }
        steps = [DummyStep('step1', {}), DummyStep('step2', {})]
        pipeline = Pipeline('test', steps, flow, ServiceRegistry())

        # Should initialize detector but find no loops
        assert pipeline.loop_detector is not None
        assert pipeline.has_loops() is False  # No actual loops detected
        assert pipeline.get_loops() == []
        assert pipeline.loop_executor is None  # No executor if no loops

    def test_pipeline_with_simple_loop(self):
        """Pipeline with a loop should detect it"""
        flow = {
            'start_at': 'step1',
            'paths': [
                {'from': 'step1', 'to': 'step2'},
                {'from': 'step2', 'to': 'step1', 'condition': {'type': 'expression'}},
                {'from': 'step2', 'to': 'end', 'condition': {'type': 'expression'}}
            ]
        }
        steps = [DummyStep('step1', {}), DummyStep('step2', {})]
        pipeline = Pipeline('test', steps, flow, ServiceRegistry())

        assert pipeline.has_loops() is True
        assert len(pipeline.get_loops()) == 1
        assert pipeline.loop_detector is not None
        assert pipeline.loop_executor is not None

        loop = pipeline.get_loops()[0]
        assert set(loop.steps) == {'step1', 'step2'}
        assert loop.entry_point in {'step1', 'step2'}

    def test_pipeline_with_loop_config(self):
        """Pipeline with loop_config should pass it to executor"""
        flow = {
            'start_at': 'step1',
            'paths': [
                {'from': 'step1', 'to': 'step2'},
                {'from': 'step2', 'to': 'step1', 'condition': {'type': 'expression'}},
                {'from': 'step2', 'to': 'end', 'condition': {'type': 'expression'}}
            ]
        }
        steps = [DummyStep('step1', {}), DummyStep('step2', {})]
        loop_config = {'max_iterations': 10, 'max_loop_time_seconds': 600}
        pipeline = Pipeline('test', steps, flow, ServiceRegistry(), loop_config=loop_config)

        assert pipeline.has_loops() is True
        assert pipeline.loop_executor is not None
        assert pipeline.loop_executor.loop_context.max_iterations == 10
        assert pipeline.loop_executor.loop_context.max_loop_time == 600

    def test_pipeline_with_nested_loops(self):
        """Pipeline with nested loops should detect all loops"""
        flow = {
            'start_at': 'step1',
            'paths': [
                {'from': 'step1', 'to': 'step2'},
                {'from': 'step2', 'to': 'step3'},
                {'from': 'step3', 'to': 'step2', 'condition': {'type': 'expression'}},  # Inner loop
                {'from': 'step3', 'to': 'step4', 'condition': {'type': 'expression'}},
                {'from': 'step4', 'to': 'step1', 'condition': {'type': 'expression'}},  # Outer loop
                {'from': 'step4', 'to': 'end', 'condition': {'type': 'expression'}}
            ]
        }
        steps = [
            DummyStep('step1', {}),
            DummyStep('step2', {}),
            DummyStep('step3', {}),
            DummyStep('step4', {})
        ]
        pipeline = Pipeline('test', steps, flow, ServiceRegistry())

        assert pipeline.has_loops() is True
        loops = pipeline.get_loops()
        assert len(loops) >= 1  # At least one loop detected

    def test_pipeline_paths_vs_transitions(self):
        """Pipeline with 'paths' should work with from/to format"""
        flow = {
            'start_at': 'step1',
            'paths': [
                {'from': 'step1', 'to': 'step2'},
                {'from': 'step2', 'to': 'step1', 'condition': {'type': 'expression'}},
                {'from': 'step2', 'to': 'end', 'condition': {'type': 'expression'}}
            ]
        }
        steps = [DummyStep('step1', {}), DummyStep('step2', {})]
        pipeline = Pipeline('test', steps, flow, ServiceRegistry())

        assert pipeline is not None

    def test_pipeline_empty_transitions(self):
        """Pipeline with empty transitions list should not have loops"""
        flow = {
            'start_at': 'step1',
            'paths': []
        }
        steps = [DummyStep('step1', {})]
        pipeline = Pipeline('test', steps, flow, ServiceRegistry())

        assert pipeline.has_loops() is False
        assert pipeline.get_loops() == []

    def test_pipeline_loop_detector_exists_without_loops(self):
        """Pipeline should initialize detector but has_loops() returns False if no loops found"""
        flow = {
            'start_at': 'step1',
            'paths': [
                {'from': 'step1', 'to': 'step2'},
                {'from': 'step2', 'to': 'step3'}
            ]
        }
        steps = [DummyStep('step1', {}), DummyStep('step2', {}), DummyStep('step3', {})]
        pipeline = Pipeline('test', steps, flow, ServiceRegistry())

        # Detector may exist, but has_loops() checks executor (which only exists if loops found)
        assert pipeline.has_loops() is False
        assert pipeline.loop_executor is None


class TestPipelineLoopBackwardCompatibility:
    """Test backward compatibility with existing pipelines"""

    def test_existing_pipeline_without_loop_config(self):
        """Existing pipelines without loop_config should work"""
        flow = {'start_at': 'step1'}
        steps = [DummyStep('step1', {})]

        # Old-style initialization (no loop_config)
        pipeline = Pipeline('test', steps, flow, ServiceRegistry())

        assert pipeline.loop_config == {}
        assert pipeline.has_loops() is False

    @pytest.mark.asyncio
    async def test_existing_pipeline_execution(self):
        """Existing pipelines should execute normally"""
        flow = {'start_at': 'step1'}
        steps = [DummyStep('step1', {})]
        pipeline = Pipeline('test', steps, flow, ServiceRegistry())

        # Should execute without issues
        result = await pipeline.run({'input': 'test'}, create_test_execution_context())
        assert result is not None
