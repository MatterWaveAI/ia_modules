"""
Unit tests for InMemoryExecutionTracker

Tests the in-memory execution tracking implementation used for tests.
"""

import pytest
import asyncio
from datetime import datetime
from ia_modules.pipeline.in_memory_tracker import InMemoryExecutionTracker


class TestInMemoryExecutionTracker:
    """Test suite for InMemoryExecutionTracker"""

    @pytest.fixture
    def tracker(self):
        """Create a fresh tracker instance for each test"""
        return InMemoryExecutionTracker()

    @pytest.mark.asyncio
    async def test_start_execution_generates_id(self, tracker):
        """Test that start_execution generates an execution ID"""
        execution_id = await tracker.start_execution(
            pipeline_name="test_pipeline",
            pipeline_version="1.0",
            input_data={"key": "value"}
        )
        
        assert execution_id is not None
        assert isinstance(execution_id, str)
        assert len(execution_id) > 0
        assert tracker.current_execution_id == execution_id

    @pytest.mark.asyncio
    async def test_start_execution_with_custom_id(self, tracker):
        """Test that start_execution accepts custom execution ID"""
        custom_id = "custom-execution-123"
        execution_id = await tracker.start_execution(
            pipeline_name="test_pipeline",
            execution_id=custom_id
        )
        
        assert execution_id == custom_id
        assert tracker.current_execution_id == custom_id

    @pytest.mark.asyncio
    async def test_start_execution_stores_data(self, tracker):
        """Test that start_execution stores execution data"""
        input_data = {"topic": "AI", "count": 10}
        execution_id = await tracker.start_execution(
            pipeline_name="test_pipeline",
            pipeline_version="2.0",
            input_data=input_data
        )
        
        execution = tracker.get_execution(execution_id)
        assert execution is not None
        assert execution['pipeline_name'] == "test_pipeline"
        assert execution['pipeline_version'] == "2.0"
        assert execution['input_data'] == input_data
        assert execution['status'] == 'running'
        assert isinstance(execution['start_time'], datetime)
        assert execution['end_time'] is None

    @pytest.mark.asyncio
    async def test_start_step_execution(self, tracker):
        """Test starting a step execution"""
        execution_id = await tracker.start_execution(pipeline_name="test_pipeline")
        
        step_execution_id = await tracker.start_step_execution(
            execution_id=execution_id,
            step_name="step1",
            step_id="step1",
            input_data={"input": "data"}
        )
        
        assert step_execution_id is not None
        assert execution_id in step_execution_id
        assert "step1" in step_execution_id

    @pytest.mark.asyncio
    async def test_start_step_execution_stores_data(self, tracker):
        """Test that start_step_execution stores step data"""
        execution_id = await tracker.start_execution(pipeline_name="test_pipeline")
        input_data = {"field": "value"}
        
        step_execution_id = await tracker.start_step_execution(
            execution_id=execution_id,
            step_name="process_step",
            step_id="step2",
            input_data=input_data
        )
        
        step = tracker.steps[step_execution_id]
        assert step['execution_id'] == execution_id
        assert step['step_name'] == "process_step"
        assert step['step_id'] == "step2"
        assert step['input_data'] == input_data
        assert step['status'] == 'running'
        assert isinstance(step['start_time'], datetime)
        assert step['end_time'] is None

    @pytest.mark.asyncio
    async def test_complete_step_execution_success(self, tracker):
        """Test completing a step execution successfully"""
        execution_id = await tracker.start_execution(pipeline_name="test_pipeline")
        step_execution_id = await tracker.start_step_execution(
            execution_id=execution_id,
            step_name="step1",
            step_id="step1"
        )
        
        output_data = {"result": "success", "count": 5}
        await tracker.complete_step_execution(
            step_execution_id=step_execution_id,
            output_data=output_data,
            status='completed'
        )
        
        step = tracker.steps[step_execution_id]
        assert step['output_data'] == output_data
        assert step['status'] == 'completed'
        assert isinstance(step['end_time'], datetime)
        assert step['error'] is None

    @pytest.mark.asyncio
    async def test_complete_step_execution_failure(self, tracker):
        """Test completing a step execution with failure"""
        execution_id = await tracker.start_execution(pipeline_name="test_pipeline")
        step_execution_id = await tracker.start_step_execution(
            execution_id=execution_id,
            step_name="step1",
            step_id="step1"
        )
        
        error_msg = "Step failed due to invalid input"
        await tracker.complete_step_execution(
            step_execution_id=step_execution_id,
            status='failed',
            error=error_msg
        )
        
        step = tracker.steps[step_execution_id]
        assert step['status'] == 'failed'
        assert step['error'] == error_msg
        assert isinstance(step['end_time'], datetime)

    @pytest.mark.asyncio
    async def test_update_execution_status(self, tracker):
        """Test updating execution status"""
        execution_id = await tracker.start_execution(pipeline_name="test_pipeline")
        
        await tracker.update_execution_status(
            execution_id=execution_id,
            status='running'
        )
        
        execution = tracker.get_execution(execution_id)
        assert execution['status'] == 'running'

    @pytest.mark.asyncio
    async def test_update_execution_status_with_error(self, tracker):
        """Test updating execution status with error"""
        execution_id = await tracker.start_execution(pipeline_name="test_pipeline")
        error_msg = "Pipeline failed"
        
        await tracker.update_execution_status(
            execution_id=execution_id,
            status='failed',
            error=error_msg
        )
        
        execution = tracker.get_execution(execution_id)
        assert execution['status'] == 'failed'
        assert execution['error'] == error_msg
        assert isinstance(execution['end_time'], datetime)

    def test_end_execution_success(self, tracker):
        """Test ending execution successfully"""
        execution_id = asyncio.run(tracker.start_execution(pipeline_name="test_pipeline"))
        
        tracker.end_execution(
            execution_id=execution_id,
            success=True
        )
        
        execution = tracker.get_execution(execution_id)
        assert execution['status'] == 'completed'
        assert isinstance(execution['end_time'], datetime)
        assert execution['error'] is None

    def test_end_execution_failure(self, tracker):
        """Test ending execution with failure"""
        execution_id = asyncio.run(tracker.start_execution(pipeline_name="test_pipeline"))
        error_msg = "Execution failed"
        
        tracker.end_execution(
            execution_id=execution_id,
            success=False,
            error=error_msg
        )
        
        execution = tracker.get_execution(execution_id)
        assert execution['status'] == 'failed'
        assert execution['error'] == error_msg
        assert isinstance(execution['end_time'], datetime)

    @pytest.mark.asyncio
    async def test_log_message(self, tracker):
        """Test logging messages"""
        execution_id = await tracker.start_execution(pipeline_name="test_pipeline")
        
        await tracker.log_message(
            execution_id=execution_id,
            level="INFO",
            message="Test log message",
            step_name="step1",
            data={"key": "value"}
        )
        
        logs = tracker.get_logs(execution_id)
        assert len(logs) == 1
        assert logs[0]['level'] == "INFO"
        assert logs[0]['message'] == "Test log message"
        assert logs[0]['step_name'] == "step1"
        assert logs[0]['data'] == {"key": "value"}
        assert isinstance(logs[0]['timestamp'], datetime)

    @pytest.mark.asyncio
    async def test_get_step_executions(self, tracker):
        """Test getting all step executions for an execution"""
        execution_id = await tracker.start_execution(pipeline_name="test_pipeline")
        
        # Create multiple steps
        step1_id = await tracker.start_step_execution(
            execution_id=execution_id,
            step_name="step1",
            step_id="step1"
        )
        step2_id = await tracker.start_step_execution(
            execution_id=execution_id,
            step_name="step2",
            step_id="step2"
        )
        
        steps = tracker.get_step_executions(execution_id)
        assert len(steps) == 2
        assert any(s['step_execution_id'] == step1_id for s in steps)
        assert any(s['step_execution_id'] == step2_id for s in steps)

    @pytest.mark.asyncio
    async def test_get_all_executions(self, tracker):
        """Test getting all executions"""
        exec1_id = await tracker.start_execution(pipeline_name="pipeline1")
        exec2_id = await tracker.start_execution(pipeline_name="pipeline2")
        
        executions = tracker.get_all_executions()
        assert len(executions) == 2
        assert any(e['execution_id'] == exec1_id for e in executions)
        assert any(e['execution_id'] == exec2_id for e in executions)

    @pytest.mark.asyncio
    async def test_get_all_steps(self, tracker):
        """Test getting all step executions"""
        exec_id = await tracker.start_execution(pipeline_name="test_pipeline")
        
        await tracker.start_step_execution(exec_id, "step1", "step1")
        await tracker.start_step_execution(exec_id, "step2", "step2")
        
        all_steps = tracker.get_all_steps()
        assert len(all_steps) == 2

    def test_clear(self, tracker):
        """Test clearing all data"""
        exec_id = asyncio.run(tracker.start_execution(pipeline_name="test_pipeline"))
        asyncio.run(tracker.start_step_execution(exec_id, "step1", "step1"))
        asyncio.run(tracker.log_message(exec_id, "INFO", "test"))
        
        tracker.clear()
        
        assert len(tracker.executions) == 0
        assert len(tracker.steps) == 0
        assert len(tracker.logs) == 0
        assert tracker.current_execution_id is None

    def test_set_execution_id(self, tracker):
        """Test setting current execution ID"""
        test_id = "test-execution-123"
        tracker.set_execution_id(test_id)
        
        assert tracker.current_execution_id == test_id

    @pytest.mark.asyncio
    async def test_multiple_executions_isolated(self, tracker):
        """Test that multiple executions are properly isolated"""
        exec1_id = await tracker.start_execution(pipeline_name="pipeline1")
        step1_id = await tracker.start_step_execution(exec1_id, "step1", "step1")
        await tracker.log_message(exec1_id, "INFO", "exec1 log")
        
        exec2_id = await tracker.start_execution(pipeline_name="pipeline2")
        step2_id = await tracker.start_step_execution(exec2_id, "step2", "step2")
        await tracker.log_message(exec2_id, "INFO", "exec2 log")
        
        # Verify isolation
        exec1_steps = tracker.get_step_executions(exec1_id)
        exec2_steps = tracker.get_step_executions(exec2_id)
        
        assert len(exec1_steps) == 1
        assert len(exec2_steps) == 1
        assert exec1_steps[0]['step_execution_id'] == step1_id
        assert exec2_steps[0]['step_execution_id'] == step2_id
        
        exec1_logs = tracker.get_logs(exec1_id)
        exec2_logs = tracker.get_logs(exec2_id)
        
        assert len(exec1_logs) == 1
        assert len(exec2_logs) == 1
        assert exec1_logs[0]['message'] == "exec1 log"
        assert exec2_logs[0]['message'] == "exec2 log"

    @pytest.mark.asyncio
    async def test_complete_pipeline_flow(self, tracker):
        """Test a complete pipeline execution flow"""
        # Start execution
        execution_id = await tracker.start_execution(
            pipeline_name="complete_pipeline",
            pipeline_version="1.0",
            input_data={"input": "data"}
        )
        
        # Execute steps
        step1_id = await tracker.start_step_execution(
            execution_id=execution_id,
            step_name="fetch_data",
            step_id="step1",
            input_data={"query": "test"}
        )
        await tracker.complete_step_execution(
            step_execution_id=step1_id,
            output_data={"records": 10},
            status='completed'
        )
        
        step2_id = await tracker.start_step_execution(
            execution_id=execution_id,
            step_name="process_data",
            step_id="step2",
            input_data={"records": 10}
        )
        await tracker.complete_step_execution(
            step_execution_id=step2_id,
            output_data={"processed": 10},
            status='completed'
        )
        
        # Log messages
        await tracker.log_message(execution_id, "INFO", "Processing started")
        await tracker.log_message(execution_id, "INFO", "Processing completed")
        
        # End execution
        tracker.end_execution(execution_id, success=True)
        
        # Verify final state
        execution = tracker.get_execution(execution_id)
        assert execution['status'] == 'completed'
        assert execution['end_time'] is not None
        
        steps = tracker.get_step_executions(execution_id)
        assert len(steps) == 2
        assert all(s['status'] == 'completed' for s in steps)
        
        logs = tracker.get_logs(execution_id)
        assert len(logs) == 2


    async def test_status_updates_accept_enum_members(self, tracker):
        """The runner passes ExecutionStatus/StepStatus members; they are stored as text"""
        from ia_modules.pipeline.execution_tracker import ExecutionStatus, StepStatus

        execution_id = await tracker.start_execution("pipeline")
        step_id = await tracker.start_step_execution(execution_id, "step", "step-1")
        await tracker.complete_step_execution(step_id, status=StepStatus.COMPLETED)
        await tracker.update_execution_status(execution_id, ExecutionStatus.COMPLETED)

        assert tracker.get_all_executions()[0]['status'] == 'completed'
        assert tracker.get_all_steps()[0]['status'] == 'completed'


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
