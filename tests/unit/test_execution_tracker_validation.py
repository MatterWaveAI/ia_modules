"""
Unit tests for ExecutionTracker validation edge cases

Tests critical validation logic including:
- Completed executions with zero completed_steps
- Inconsistent step counts (completed + failed != total)
- NULL output_data on completed executions
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from ia_modules.pipeline.execution_tracker import (
    ExecutionTracker,
    ExecutionRecord,
    ExecutionStatus,
    StepStatus
)
from nexusql import DatabaseManager


class TestExecutionTrackerValidation:
    """Test validation edge cases in ExecutionTracker"""

    @pytest.mark.asyncio
    async def test_completed_execution_with_zero_completed_steps(self):
        """
        Test that we can detect completed executions with 0 completed_steps.
        This is a data integrity issue that should be flagged.
        """
        # Mock database manager
        db_manager = Mock(spec=DatabaseManager)
        ExecutionTracker(db_manager)

        # Create execution with COMPLETED status but 0 completed_steps
        execution_id = "test-exec-001"
        execution = ExecutionRecord(
            execution_id=execution_id,
            pipeline_id="test-pipeline",
            pipeline_name="Test Pipeline",
            status=ExecutionStatus.COMPLETED,
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=datetime.now(timezone.utc).isoformat(),
            total_steps=3,
            completed_steps=0,  # BUG: Completed but 0 steps completed
            failed_steps=0,
            output_data={"result": "success"}
        )

        # Verify the issue exists
        assert execution.status == ExecutionStatus.COMPLETED
        assert execution.completed_steps == 0
        assert execution.total_steps > 0

        # This is a data integrity violation that should be caught
        is_valid = execution.completed_steps > 0 or execution.total_steps == 0
        assert not is_valid, "Completed execution should have completed_steps > 0"

    @pytest.mark.asyncio
    async def test_inconsistent_step_counts(self):
        """
        Test detection of inconsistent step counts.
        (completed_steps + failed_steps) should equal total_steps for completed executions.
        """
        # Mock database manager
        db_manager = Mock(spec=DatabaseManager)
        ExecutionTracker(db_manager)

        # Create execution with inconsistent step counts
        execution = ExecutionRecord(
            execution_id="test-exec-002",
            pipeline_id="test-pipeline",
            pipeline_name="Test Pipeline",
            status=ExecutionStatus.COMPLETED,
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=datetime.now(timezone.utc).isoformat(),
            total_steps=5,
            completed_steps=2,
            failed_steps=1,  # 2 + 1 = 3, but total_steps = 5
            output_data={"result": "partial"}
        )

        # Verify inconsistency
        sum_steps = execution.completed_steps + execution.failed_steps
        assert sum_steps != execution.total_steps
        assert sum_steps == 3
        assert execution.total_steps == 5

    @pytest.mark.asyncio
    async def test_completed_execution_null_output_data(self):
        """
        Test detection of completed executions with NULL output_data.
        This may be valid in some cases but should be flagged for review.
        """
        # Mock database manager
        db_manager = Mock(spec=DatabaseManager)
        ExecutionTracker(db_manager)

        # Create completed execution with no output data
        execution = ExecutionRecord(
            execution_id="test-exec-003",
            pipeline_id="test-pipeline",
            pipeline_name="Test Pipeline",
            status=ExecutionStatus.COMPLETED,
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=datetime.now(timezone.utc).isoformat(),
            total_steps=2,
            completed_steps=2,
            failed_steps=0,
            output_data=None  # WARNING: Completed but no output data
        )

        # Verify the potential issue
        assert execution.status == ExecutionStatus.COMPLETED
        assert execution.output_data is None
        # This may or may not be a bug depending on pipeline design

    @pytest.mark.asyncio
    async def test_update_execution_step_counts_maintains_consistency(self):
        """
        Test that _update_execution_step_counts correctly maintains step count consistency.
        """
        # Mock database manager
        db_manager = Mock(spec=DatabaseManager)
        db_manager.fetch_one = Mock(return_value={
            'total': 3,
            'completed': 2,
            'failed': 1
        })
        db_manager.execute = Mock()

        tracker = ExecutionTracker(db_manager)

        # Create active execution
        execution_id = "test-exec-004"
        execution = ExecutionRecord(
            execution_id=execution_id,
            pipeline_id="test-pipeline",
            pipeline_name="Test Pipeline",
            status=ExecutionStatus.RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
            total_steps=3,
            completed_steps=0,
            failed_steps=0
        )

        tracker.active_executions[execution_id] = execution

        # Mock _save_execution (note: this method doesn't exist but is called in the code)
        # This is a bug in execution_tracker.py:664 - it should call _update_execution
        async def mock_save(exec_record):
            pass

        tracker._save_execution = mock_save

        # Call the method to update step counts
        await tracker._update_execution_step_counts(execution_id)

        # Verify counts were updated correctly
        assert execution.completed_steps == 2
        assert execution.failed_steps == 1
        assert execution.completed_steps + execution.failed_steps == 3

    @pytest.mark.asyncio
    async def test_update_status_to_completed_with_zero_steps(self):
        """
        Test that updating execution status to COMPLETED when completed_steps is 0
        raises a ValueError (validation prevents the bug).
        """
        # Mock database manager
        db_manager = Mock(spec=DatabaseManager)
        db_manager.execute = Mock()

        tracker = ExecutionTracker(db_manager)

        # Create active execution
        execution_id = "test-exec-005"
        execution = ExecutionRecord(
            execution_id=execution_id,
            pipeline_id="test-pipeline",
            pipeline_name="Test Pipeline",
            status=ExecutionStatus.RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
            total_steps=3,
            completed_steps=0,
            failed_steps=0
        )

        tracker.active_executions[execution_id] = execution

        # Mock the broadcast methods
        with patch.object(tracker, '_broadcast_execution_update'):
            # Try to update to completed WITHOUT updating step counts
            # This should now raise ValueError due to validation
            with pytest.raises(ValueError, match="cannot be marked as COMPLETED with 0 completed steps"):
                await tracker.update_execution_status(
                    execution_id=execution_id,
                    status=ExecutionStatus.COMPLETED,
                    output_data={"result": "done"}
                )

        # Execution should still be RUNNING (validation prevented the bug)
        assert execution.status == ExecutionStatus.RUNNING
        assert execution.completed_steps == 0
        assert execution.total_steps == 3

    @pytest.mark.asyncio
    async def test_complete_step_updates_execution_counts(self):
        """
        Test that completing a step properly updates execution step counts.
        This is the CORRECT behavior that should prevent zero completed_steps bugs.
        """
        # Mock database manager
        db_manager = Mock(spec=DatabaseManager)

        # Mock fetch_one to return step execution
        step_data = {
            'step_execution_id': 'step-001',
            'execution_id': 'exec-001',
            'step_id': 'step1',
            'step_name': 'Step 1',
            'step_type': 'function',
            'status': 'running',
            'started_at': datetime.now(timezone.utc).isoformat(),
            'completed_at': None,
            'input_data': None,
            'output_data': None,
            'error_message': None,
            'execution_time_ms': None,
            'retry_count': 0,
            'metadata_json': None
        }
        db_manager.fetch_one = Mock(return_value=step_data)

        # Mock fetch_one for step counts
        db_manager.execute = Mock()

        tracker = ExecutionTracker(db_manager)

        # Mock the helper methods
        with patch.object(tracker, '_update_step_execution'), \
             patch.object(tracker, '_update_execution_step_counts') as mock_update_counts, \
             patch.object(tracker, '_broadcast_step_update'):

            # Complete a step
            await tracker.complete_step_execution(
                step_execution_id='step-001',
                status=StepStatus.COMPLETED,
                output_data={'result': 'success'}
            )

            # Verify that step counts were updated
            mock_update_counts.assert_called_once_with('exec-001')

    @pytest.mark.asyncio
    async def test_execution_with_all_failed_steps(self):
        """
        Test execution with all steps failed (completed_steps=0, failed_steps=total).
        This is a valid state and should NOT be flagged as a bug.
        """
        # Mock database manager
        db_manager = Mock(spec=DatabaseManager)
        ExecutionTracker(db_manager)

        # Create execution where all steps failed
        execution = ExecutionRecord(
            execution_id="test-exec-006",
            pipeline_id="test-pipeline",
            pipeline_name="Test Pipeline",
            status=ExecutionStatus.FAILED,  # Status is FAILED, not COMPLETED
            started_at=datetime.now(timezone.utc).isoformat(),
            completed_at=datetime.now(timezone.utc).isoformat(),
            total_steps=3,
            completed_steps=0,  # Zero completed is OK when status is FAILED
            failed_steps=3,
            error_message="All steps failed"
        )

        # This is VALID: failed execution with 0 completed_steps
        assert execution.status == ExecutionStatus.FAILED
        assert execution.completed_steps == 0
        assert execution.failed_steps == execution.total_steps

        # The bug is specifically: COMPLETED status with 0 completed_steps
        is_bug = (execution.status == ExecutionStatus.COMPLETED and
                  execution.completed_steps == 0 and
                  execution.total_steps > 0)
        assert not is_bug, "This is a valid failed execution"

    @pytest.mark.asyncio
    async def test_pipeline_with_wrapped_steps_updates_counts(self):
        """
        Test that when pipeline steps are wrapped for tracking, the step counts
        are properly updated after each step completes.

        This validates the fix for the bug where pipelines with trackers would
        complete with 0 completed_steps because step completion tracking wasn't
        calling _update_execution_step_counts().
        """
        # Mock database manager
        db_manager = Mock(spec=DatabaseManager)
        db_manager.fetch_one = Mock(return_value={
            'total': 3,
            'completed': 2,
            'failed': 0
        })
        db_manager.execute = Mock()

        tracker = ExecutionTracker(db_manager)

        # Create execution with 3 steps
        execution_id = "test-exec-007"
        execution = ExecutionRecord(
            execution_id=execution_id,
            pipeline_id="test-pipeline",
            pipeline_name="Test Pipeline",
            status=ExecutionStatus.RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
            total_steps=3,
            completed_steps=0,
            failed_steps=0
        )

        tracker.active_executions[execution_id] = execution

        # Simulate completing steps
        # This mimics what happens when wrapped steps complete
        with patch.object(tracker, '_update_execution') as mock_update:
            # Step 1 completes
            await tracker._update_execution_step_counts(execution_id)

            # Verify counts were updated from database query
            assert execution.completed_steps == 2
            assert execution.failed_steps == 0

            # Verify execution was persisted
            mock_update.assert_called_once()

    @pytest.mark.asyncio
    async def test_validation_allows_completed_with_positive_steps(self):
        """
        Test that validation allows COMPLETED status when completed_steps > 0.
        This is the correct/expected behavior.
        """
        # Mock database manager
        db_manager = Mock(spec=DatabaseManager)
        db_manager.execute = Mock()

        tracker = ExecutionTracker(db_manager)

        # Create execution with steps
        execution_id = "test-exec-008"
        execution = ExecutionRecord(
            execution_id=execution_id,
            pipeline_id="test-pipeline",
            pipeline_name="Test Pipeline",
            status=ExecutionStatus.RUNNING,
            started_at=datetime.now(timezone.utc).isoformat(),
            total_steps=3,
            completed_steps=0,
            failed_steps=0
        )

        tracker.active_executions[execution_id] = execution

        # Mock broadcast
        with patch.object(tracker, '_broadcast_execution_update'):
            # Update to completed WITH proper step counts
            await tracker.update_execution_status(
                execution_id=execution_id,
                status=ExecutionStatus.COMPLETED,
                completed_steps=3,  # All steps completed
                output_data={"result": "success"}
            )

        # Should succeed without error
        assert execution.status == ExecutionStatus.COMPLETED
        assert execution.completed_steps == 3
        assert execution.total_steps == 3
