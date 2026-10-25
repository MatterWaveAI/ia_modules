"""
Tests for pipeline.execution_tracker module - Pipeline execution tracking and monitoring
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import MagicMock
from ia_modules.pipeline.execution_tracker import (
    ExecutionTracker,
    ExecutionStatus,
    StepStatus
)


class MockDatabaseManager:
    """Mock database manager for testing"""
    def __init__(self):
        self.execute_calls = []
        self.fetch_one_calls = []
        self.select_calls = []
        self.storage = {}  # Simple in-memory storage for testing

    def execute(self, query, params=None):
        # nexusql's execute returns the rows for a SELECT
        if query.lstrip().upper().startswith("SELECT"):
            self.select_calls.append((query, params))
            return []
        self.execute_calls.append((query, params))
        return MagicMock(rowcount=1)

    async def execute_async(self, query, params=None):
        self.execute_calls.append((query, params))
        return MagicMock(rowcount=1)

    def fetch_one(self, query, params=None):
        self.fetch_one_calls.append((query, params))
        return None


class MockWebSocketManager:
    """Mock WebSocket manager for testing"""
    def __init__(self):
        self.broadcasts = []

    async def broadcast_to_channel(self, channel, message):
        self.broadcasts.append((channel, message))


@pytest.mark.asyncio
class TestExecutionTracker:
    """Test ExecutionTracker class"""

    async def test_init(self):
        """Test ExecutionTracker initialization"""
        db = MockDatabaseManager()
        tracker = ExecutionTracker(db)

        assert tracker.db is db
        assert isinstance(tracker.active_executions, dict)
        assert isinstance(tracker.websocket_connections, list)
        assert len(tracker.websocket_connections) == 0

    async def test_init_with_websocket(self):
        """Test initialization with WebSocket connections list"""
        db = MockDatabaseManager()
        tracker = ExecutionTracker(db)

        # WebSocket connections start as empty list
        assert isinstance(tracker.websocket_connections, list)
        assert len(tracker.websocket_connections) == 0

    async def test_start_execution_creates_record(self):
        """Test start_execution creates new execution record"""
        db = MockDatabaseManager()
        tracker = ExecutionTracker(db)

        execution_id = await tracker.start_execution(
            pipeline_id="test-pipeline-123",
            pipeline_name="Test Pipeline",
            input_data={"key": "value"},
            total_steps=5,
            metadata={"user": "test_user"}
        )

        # Should return a valid UUID
        assert isinstance(execution_id, str)
        assert len(execution_id) == 36  # UUID format

        # Should be in active executions
        assert execution_id in tracker.active_executions
        execution = tracker.active_executions[execution_id]
        assert execution.pipeline_id == "test-pipeline-123"
        assert execution.pipeline_name == "Test Pipeline"
        assert execution.status == ExecutionStatus.RUNNING
        assert execution.total_steps == 5

    async def test_start_execution_inserts_to_database(self):
        """Test start_execution uses INSERT (not upsert)"""
        db = MockDatabaseManager()
        tracker = ExecutionTracker(db)

        await tracker.start_execution(
            pipeline_id="test-123",
            pipeline_name="Test",
            input_data={},
            total_steps=3
        )

        # Should have exactly one INSERT call
        assert len(db.execute_calls) == 1
        query, params = db.execute_calls[0]

        # Verify it's a clean INSERT
        assert "INSERT INTO pipeline_executions" in query
        assert "ON CONFLICT" not in query, "Should not use ON CONFLICT for new insertions"

        # Verify named parameters
        assert isinstance(params, dict)
        assert 'execution_id' in params
        assert 'pipeline_id' in params
        assert params['pipeline_id'] == "test-123"
        assert params['status'] == ExecutionStatus.RUNNING.value

    async def test_update_execution_status_uses_update(self):
        """Test update_execution_status uses UPDATE (not upsert)"""
        db = MockDatabaseManager()
        tracker = ExecutionTracker(db)

        # Start execution first
        execution_id = await tracker.start_execution(
            pipeline_id="test-123",
            pipeline_name="Test",
            input_data={},
            total_steps=1
        )

        # Clear previous calls
        db.execute_calls.clear()

        # Update status
        await tracker.update_execution_status(
            execution_id=execution_id,
            status=ExecutionStatus.COMPLETED,
            completed_steps=1,
            output_data={"result": "success"}
        )

        # Should have exactly one UPDATE call
        assert len(db.execute_calls) == 1
        query, params = db.execute_calls[0]

        # Verify it's a clean UPDATE
        assert "UPDATE pipeline_executions" in query
        assert "INSERT" not in query, "Should not use INSERT for updates"
        assert "ON CONFLICT" not in query, "Should not use ON CONFLICT for updates"

        # Verify named parameters
        assert isinstance(params, dict)
        assert params['execution_id'] == execution_id
        assert params['status'] == ExecutionStatus.COMPLETED.value

    async def test_update_execution_status_removes_from_active(self):
        """Test update_execution_status removes completed executions from active"""
        db = MockDatabaseManager()
        tracker = ExecutionTracker(db)

        execution_id = await tracker.start_execution(
            pipeline_id="test-123",
            pipeline_name="Test",
            input_data={},
            total_steps=1
        )

        # Should be active
        assert execution_id in tracker.active_executions

        # Complete it
        await tracker.update_execution_status(
            execution_id=execution_id,
            status=ExecutionStatus.COMPLETED,
            completed_steps=1
        )

        # Should be removed from active
        assert execution_id not in tracker.active_executions

    async def test_update_execution_keeps_failed_in_active(self):
        """Test failed executions stay in active executions"""
        db = MockDatabaseManager()
        tracker = ExecutionTracker(db)

        execution_id = await tracker.start_execution(
            pipeline_id="test-123",
            pipeline_name="Test",
            input_data={},
            total_steps=1
        )

        await tracker.update_execution_status(
            execution_id=execution_id,
            status=ExecutionStatus.FAILED,
            error_message="Test error"
        )

        # Failed executions stay in active for review
        assert execution_id in tracker.active_executions

    async def test_start_step_execution_creates_step_record(self):
        """Test start_step_execution creates new step record"""
        db = MockDatabaseManager()
        tracker = ExecutionTracker(db)

        execution_id = await tracker.start_execution(
            pipeline_id="test-123",
            pipeline_name="Test",
            input_data={},
            total_steps=2
        )

        db.execute_calls.clear()

        step_execution_id = await tracker.start_step_execution(
            execution_id=execution_id,
            step_id="step-1",
            step_name="Process Data",
            step_type="transform",
            input_data={"data": "test"}
        )

        # Should return a valid UUID
        assert isinstance(step_execution_id, str)
        assert len(step_execution_id) == 36

        # Should use INSERT
        assert len(db.execute_calls) == 1
        query, params = db.execute_calls[0]

        assert "INSERT INTO step_executions" in query
        assert "ON CONFLICT" not in query, "Should not use ON CONFLICT for new step insertions"

        # Verify named parameters
        assert isinstance(params, dict)
        assert params['step_execution_id'] == step_execution_id
        assert params['execution_id'] == execution_id
        assert params['step_name'] == "Process Data"
        assert params['status'] == StepStatus.RUNNING.value

    async def test_complete_step_execution_uses_update(self):
        """Test complete_step_execution uses UPDATE"""
        db = MockDatabaseManager()
        
        # Mock the fetch for getting step execution
        step_record = {
            'step_execution_id': 'step-uuid-123',
            'execution_id': 'exec-uuid-456',
            'step_id': 'step-1',
            'step_name': 'Test Step',
            'step_type': 'transform',
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
        db.fetch_one = MagicMock(return_value=step_record)

        tracker = ExecutionTracker(db)

        await tracker.complete_step_execution(
            step_execution_id='step-uuid-123',
            status=StepStatus.COMPLETED,
            output_data={"result": "done"}
        )

        # Should have UPDATE call
        update_calls = [call for call in db.execute_calls if "UPDATE step_executions" in call[0]]
        assert len(update_calls) >= 1

        query, params = update_calls[0]
        assert "UPDATE step_executions" in query
        assert "INSERT" not in query
        assert "ON CONFLICT" not in query, "Should not use ON CONFLICT for step updates"

        # Verify named parameters
        assert isinstance(params, dict)
        assert params['step_execution_id'] == 'step-uuid-123'
        assert params['status'] == StepStatus.COMPLETED.value

    async def test_broadcast_execution_update(self):
        """Test execution tracking without WebSocket manager"""
        db = MockDatabaseManager()
        tracker = ExecutionTracker(db)

        execution_id = await tracker.start_execution(
            pipeline_id="test-123",
            pipeline_name="Test",
            input_data={},
            total_steps=1
        )

        # Verify execution was created
        assert execution_id in tracker.active_executions
        assert tracker.active_executions[execution_id].pipeline_id == "test-123"

    async def test_broadcast_step_update(self):
        """Test step execution tracking without WebSocket manager"""
        db = MockDatabaseManager()
        tracker = ExecutionTracker(db)

        execution_id = await tracker.start_execution(
            pipeline_id="test-123",
            pipeline_name="Test",
            input_data={},
            total_steps=1
        )

        step_execution_id = await tracker.start_step_execution(
            execution_id=execution_id,
            step_id="step-1",
            step_name="Test Step",
            step_type="transform"
        )

        # Verify step execution was created
        assert isinstance(step_execution_id, str)
        assert len(step_execution_id) == 36  # UUID format

    async def test_get_recent_executions_uses_named_params(self):
        """Test get_recent_executions uses named parameters"""
        db = MockDatabaseManager()
        tracker = ExecutionTracker(db)

        await tracker.get_recent_executions(limit=10)

        assert len(db.select_calls) == 1
        query, params = db.select_calls[0]

        # Should use named parameter for LIMIT
        assert "LIMIT :limit" in query
        assert isinstance(params, dict)
        assert params['limit'] == 10

    async def test_load_active_executions_uses_named_params(self):
        """Test _load_active_executions uses named parameters"""
        db = MockDatabaseManager()
        tracker = ExecutionTracker(db)

        await tracker._load_active_executions()

        assert len(db.select_calls) == 1
        query, params = db.select_calls[0]

        # Should use named parameters for IN clause
        assert ":status1" in query or ":status2" in query
        assert isinstance(params, dict)

    async def test_get_execution_uses_named_params(self):
        """Test get_execution uses named parameters"""
        db = MockDatabaseManager()
        tracker = ExecutionTracker(db)

        await tracker.get_execution("test-execution-id")

        assert len(db.fetch_one_calls) == 1
        query, params = db.fetch_one_calls[0]

        # Should use named parameter
        assert ":execution_id" in query
        assert isinstance(params, dict)
        assert params['execution_id'] == "test-execution-id"


@pytest.mark.asyncio
class TestExecutionStatusEnum:
    """Test ExecutionStatus enum"""

    async def test_execution_status_values(self):
        """Test ExecutionStatus enum values"""
        assert ExecutionStatus.PENDING.value == "pending"
        assert ExecutionStatus.RUNNING.value == "running"
        assert ExecutionStatus.COMPLETED.value == "completed"
        assert ExecutionStatus.FAILED.value == "failed"
        assert ExecutionStatus.CANCELLED.value == "cancelled"


@pytest.mark.asyncio
class TestStepStatusEnum:
    """Test StepStatus enum"""

    async def test_step_status_values(self):
        """Test StepStatus enum values"""
        assert StepStatus.PENDING.value == "pending"
        assert StepStatus.RUNNING.value == "running"
        assert StepStatus.COMPLETED.value == "completed"
        assert StepStatus.FAILED.value == "failed"
        assert StepStatus.SKIPPED.value == "skipped"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
