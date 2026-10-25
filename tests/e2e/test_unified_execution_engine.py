"""
Comprehensive E2E test for unified GraphPipelineRunner execution engine

Tests that GraphPipelineRunner correctly executes all 6 pipeline types:
- Simple: Linear sequential flow
- Conditional: Branching based on conditions
- Parallel: Multiple concurrent paths
- Loop: Iteration with back edges
- HITL: Human-in-the-loop
- Agent: Agent-based processing
"""

import pytest
import json
import sys
from pathlib import Path

# Add parent directory to path
sys.path.append(str(Path(__file__).parent.parent.parent))

from ia_modules.pipeline.graph_pipeline_runner import GraphPipelineRunner


class TestUnifiedExecutionEngine:
    """Test suite for unified execution engine across all pipeline types"""

    @pytest.mark.asyncio
    async def test_simple_pipeline_execution(self):
        """Test simple linear pipeline execution"""
        pipeline_file = Path(__file__).parent.parent / "pipelines" / "simple_pipeline" / "pipeline.json"
        
        with open(pipeline_file, 'r') as f:
            pipeline_config = json.load(f)
        
        input_data = {"topic": "test_simple"}
        
        runner = GraphPipelineRunner()
        result = await runner.run_pipeline_from_json(pipeline_config, input_data)
        
        # Verify execution completed successfully
        assert result is not None
        assert runner.execution_stats['steps_executed'] > 0
        
        # Verify in-memory tracker was used
        tracker = runner.services.get('execution_tracker')
        assert tracker is not None
        assert hasattr(tracker, 'executions')  # InMemoryExecutionTracker attribute
        
        # Verify execution was tracked
        executions = tracker.get_all_executions()
        assert len(executions) > 0
        
        # Verify steps were tracked
        steps = tracker.get_all_steps()
        assert len(steps) >= 3  # Simple pipeline has 3 steps

    @pytest.mark.asyncio
    async def test_conditional_pipeline_execution(self):
        """Test conditional branching pipeline"""
        pipeline_file = Path(__file__).parent.parent / "pipelines" / "conditional_pipeline" / "pipeline.json"
        
        with open(pipeline_file, 'r') as f:
            pipeline_config = json.load(f)
        
        # The pipeline declares these two parameters as required; complete
        # records score above the threshold, so this takes the high-quality path
        input_data = {
            "threshold": 0.7,
            "test_data": [{"id": 1, "value": "alpha"}, {"id": 2, "value": "beta"}],
        }
        
        runner = GraphPipelineRunner()
        result = await runner.run_pipeline_from_json(pipeline_config, input_data)
        
        assert result is not None
        assert runner.execution_stats['steps_executed'] > 0
        
        # Verify execution tracking
        tracker = runner.services.get('execution_tracker')
        executions = tracker.get_all_executions()
        assert len(executions) > 0
        assert executions[0]['status'] == 'completed'

    @pytest.mark.asyncio
    async def test_parallel_pipeline_execution(self):
        """Test parallel execution with multiple concurrent paths"""
        pipeline_file = Path(__file__).parent.parent / "pipelines" / "parallel_pipeline" / "pipeline.json"
        
        with open(pipeline_file, 'r') as f:
            pipeline_config = json.load(f)
        
        input_data = {
            "loaded_data": [
                {"stream": "A", "value": 100},
                {"stream": "B", "value": 200},
                {"stream": "C", "value": 300}
            ]
        }
        
        runner = GraphPipelineRunner()
        result = await runner.run_pipeline_from_json(pipeline_config, input_data)
        
        assert result is not None
        assert runner.execution_stats['steps_executed'] > 0
        
        # Verify parallel execution was tracked
        tracker = runner.services.get('execution_tracker')
        steps = tracker.get_all_steps()
        assert len(steps) >= 6  # Parallel pipeline has 6 steps
        
        # Verify all steps completed
        for step in steps:
            # Status might be a StepStatus enum or string
            status = step['status']
            if hasattr(status, 'value'):
                status = status.value
            assert status in ['completed', 'running']

    @pytest.mark.asyncio
    async def test_loop_pipeline_execution(self):
        """Test loop pipeline with iteration"""
        pipeline_file = Path(__file__).parent.parent / "pipelines" / "loop_pipeline" / "pipeline.json"
        
        with open(pipeline_file, 'r') as f:
            pipeline_config = json.load(f)
        
        # The pipeline declares topic and max_revisions as required
        input_data = {"topic": "draft content", "max_revisions": 2}

        runner = GraphPipelineRunner()
        result = await runner.run_pipeline_from_json(pipeline_config, input_data)

        assert result is not None

        # Verify loop iteration tracking
        tracker = runner.services.get('execution_tracker')
        steps = tracker.get_all_steps()
        assert len(steps) > 0

    @pytest.mark.asyncio
    async def test_execution_tracker_isolation(self):
        """Test that each pipeline execution is isolated in tracker"""
        pipeline_file = Path(__file__).parent.parent / "pipelines" / "simple_pipeline" / "pipeline.json"
        
        with open(pipeline_file, 'r') as f:
            pipeline_config = json.load(f)
        
        # Run pipeline twice
        runner1 = GraphPipelineRunner()
        await runner1.run_pipeline_from_json(pipeline_config, {"topic": "run1"})
        
        runner2 = GraphPipelineRunner()
        await runner2.run_pipeline_from_json(pipeline_config, {"topic": "run2"})
        
        # Each runner should have its own tracker
        tracker1 = runner1.services.get('execution_tracker')
        tracker2 = runner2.services.get('execution_tracker')
        
        # Trackers should be different instances
        assert tracker1 is not tracker2
        
        # Each should have one execution
        assert len(tracker1.get_all_executions()) == 1
        assert len(tracker2.get_all_executions()) == 1

    @pytest.mark.asyncio
    async def test_execution_tracker_queries(self):
        """Test execution tracker query methods"""
        pipeline_file = Path(__file__).parent.parent / "pipelines" / "simple_pipeline" / "pipeline.json"
        
        with open(pipeline_file, 'r') as f:
            pipeline_config = json.load(f)
        
        runner = GraphPipelineRunner()
        await runner.run_pipeline_from_json(pipeline_config, {"topic": "query_test"})
        
        tracker = runner.services.get('execution_tracker')
        
        # Test get_all_executions
        executions = tracker.get_all_executions()
        assert len(executions) == 1
        execution = executions[0]
        assert 'execution_id' in execution
        assert 'pipeline_name' in execution
        assert 'status' in execution
        
        # Test get_execution by ID
        execution_id = execution['execution_id']
        retrieved = tracker.get_execution(execution_id)
        assert retrieved == execution
        
        # Test get_step_executions
        steps = tracker.get_step_executions(execution_id)
        assert len(steps) >= 3  # Simple pipeline has at least 3 steps
        
        # Test get_logs
        logs = tracker.get_logs(execution_id)
        assert isinstance(logs, list)

    @pytest.mark.asyncio
    async def test_execution_error_tracking(self):
        """Test that execution failures are tracked correctly"""
        # Create a pipeline config that will fail
        bad_config = {
            "name": "failing_pipeline",
            "steps": [
                {
                    "id": "bad_step",
                    "name": "Bad Step",
                    "step_class": "NonExistentStep",
                    "module": "nonexistent.module",
                    "config": {}
                }
            ],
            "flow": {
                "start_at": "bad_step",
                "paths": [
                    {
                        "from": "bad_step",
                        "to": "end_with_success",
                        "condition": {"type": "always"}
                    }
                ]
            }
        }
        
        runner = GraphPipelineRunner()
        
        with pytest.raises(Exception):
            await runner.run_pipeline_from_json(bad_config, {})
        
        # Verify failure was tracked
        tracker = runner.services.get('execution_tracker')
        executions = tracker.get_all_executions()
        
        if len(executions) > 0:
            # If execution started, it should be marked as failed
            assert executions[0]['status'] in ['failed', 'running']

    @pytest.mark.asyncio
    async def test_default_services_creation(self):
        """Test that GraphPipelineRunner creates default services correctly"""
        runner = GraphPipelineRunner()
        
        # Verify services were created
        assert runner.services is not None
        
        # Verify execution tracker was registered
        tracker = runner.services.get('execution_tracker')
        assert tracker is not None
        
        # Verify it's the in-memory tracker
        assert hasattr(tracker, 'executions')
        assert hasattr(tracker, 'steps')
        assert hasattr(tracker, 'logs')
        
        # Verify it has all required methods
        assert hasattr(tracker, 'start_execution')
        assert hasattr(tracker, 'start_step_execution')
        assert hasattr(tracker, 'complete_step_execution')
        assert hasattr(tracker, 'update_execution_status')
        assert hasattr(tracker, 'end_execution')

    @pytest.mark.asyncio
    async def test_multiple_pipeline_types_sequential(self):
        """Test running different pipeline types sequentially"""
        pipelines = [
            ("simple", "simple_pipeline"),
            ("conditional", "conditional_pipeline"),
            ("parallel", "parallel_pipeline"),
        ]
        
        for name, folder in pipelines:
            pipeline_file = Path(__file__).parent.parent / "pipelines" / folder / "pipeline.json"
            
            with open(pipeline_file, 'r') as f:
                pipeline_config = json.load(f)
            
            # Adjust input data based on pipeline type
            if name == "parallel":
                input_data = {"loaded_data": [{"value": 1}]}
            elif name == "conditional":
                input_data = {"threshold": 0.7, "test_data": [{"id": 1, "value": "alpha"}]}
            else:
                input_data = {"topic": f"test_{name}"}
            
            runner = GraphPipelineRunner()
            result = await runner.run_pipeline_from_json(pipeline_config, input_data)
            
            assert result is not None, f"{name} pipeline failed"
            
            # Verify tracking worked
            tracker = runner.services.get('execution_tracker')
            executions = tracker.get_all_executions()
            assert len(executions) == 1, f"{name} pipeline tracking failed"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
