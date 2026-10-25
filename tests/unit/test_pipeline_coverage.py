"""
Comprehensive unit tests for pipeline modules:
- ia_modules/pipeline/execution_tracker.py
- ia_modules/pipeline/iterative_refinement.py
- ia_modules/pipeline/runner.py
"""

import json
import uuid
from datetime import datetime, timezone
from unittest.mock import MagicMock, AsyncMock, patch

import pytest

from ia_modules.pipeline.execution_tracker import (
    ExecutionStatus,
    StepStatus,
    ExecutionRecord,
    StepExecutionRecord,
    ExecutionTracker,
    get_execution_tracker,
    initialize_execution_tracker,
)
from ia_modules.pipeline.iterative_refinement import (
    IterativeRefinementStep,
    ProcessRefinementResponseStep,
)
from ia_modules.pipeline.runner import (
    load_step_class,
    load_step_class_async,
    create_step_from_json,
    create_step_from_json_async,
    create_pipeline_from_json,
    run_pipeline_from_json,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_db_row(**overrides):
    """Create a fake database row dict for pipeline_executions."""
    defaults = {
        "execution_id": str(uuid.uuid4()),
        "pipeline_id": "pipe-1",
        "pipeline_name": "Test Pipeline",
        "status": "running",
        "started_at": "2025-01-01T00:00:00",
        "completed_at": None,
        "total_steps": 2,
        "completed_steps": 0,
        "failed_steps": 0,
        "input_data": None,
        "output_data": None,
        "error_message": None,
        "execution_time_ms": None,
        "metadata_json": None,
    }
    defaults.update(overrides)
    return defaults


def _make_step_row(**overrides):
    """Create a fake database row dict for step_executions."""
    defaults = {
        "step_execution_id": str(uuid.uuid4()),
        "execution_id": str(uuid.uuid4()),
        "step_id": "step-1",
        "step_name": "Test Step",
        "step_type": "process",
        "status": "running",
        "started_at": "2025-01-01T00:00:00",
        "completed_at": None,
        "input_data": None,
        "output_data": None,
        "error_message": None,
        "execution_time_ms": None,
        "retry_count": 0,
        "metadata_json": None,
    }
    defaults.update(overrides)
    return defaults


def _mock_db():
    db = MagicMock()
    db.fetch_one = MagicMock(return_value=None)
    db.execute = MagicMock(return_value=[])
    db.execute_async = AsyncMock()
    return db


# ===================================================================
# ExecutionRecord / StepExecutionRecord dataclass tests
# ===================================================================

class TestExecutionRecord:
    def test_to_dict_serialises_status(self):
        rec = ExecutionRecord(
            execution_id="e1",
            pipeline_id="p1",
            pipeline_name="Test",
            status=ExecutionStatus.RUNNING,
            started_at="2025-01-01T00:00:00",
        )
        d = rec.to_dict()
        assert d["status"] == "running"
        assert d["execution_id"] == "e1"

    def test_to_dict_with_all_fields(self):
        rec = ExecutionRecord(
            execution_id="e2",
            pipeline_id="p2",
            pipeline_name="Full",
            status=ExecutionStatus.COMPLETED,
            started_at="2025-01-01T00:00:00",
            completed_at="2025-01-01T00:01:00",
            total_steps=5,
            completed_steps=5,
            failed_steps=0,
            input_data={"key": "val"},
            output_data={"out": 1},
            error_message=None,
            execution_time_ms=60000,
            metadata={"env": "test"},
        )
        d = rec.to_dict()
        assert d["status"] == "completed"
        assert d["total_steps"] == 5
        assert d["input_data"] == {"key": "val"}


class TestStepExecutionRecord:
    def test_to_dict_serialises_status(self):
        rec = StepExecutionRecord(
            step_execution_id="se1",
            execution_id="e1",
            step_id="s1",
            step_name="Step",
            step_type="process",
            status=StepStatus.COMPLETED,
            started_at="2025-01-01T00:00:00",
        )
        d = rec.to_dict()
        assert d["status"] == "completed"
        assert d["step_execution_id"] == "se1"


# ===================================================================
# ExecutionTracker tests
# ===================================================================

class TestExecutionTracker:
    def _tracker(self, db=None):
        return ExecutionTracker(db or _mock_db())

    # --- _load_active_executions ---

    async def test_load_active_executions_empty(self):
        db = _mock_db()
        db.execute.return_value = []
        tracker = self._tracker(db)
        await tracker._load_active_executions()
        assert tracker.active_executions == {}

    async def test_load_active_executions_with_rows(self):
        row = _make_db_row(
            status="running",
            input_data='{"a":1}',
            metadata_json='{"m":2}',
        )
        db = _mock_db()
        db.execute.return_value = [row]
        tracker = self._tracker(db)
        await tracker._load_active_executions()
        assert len(tracker.active_executions) == 1
        rec = list(tracker.active_executions.values())[0]
        assert rec.status == ExecutionStatus.RUNNING
        assert rec.input_data == {"a": 1}
        assert rec.metadata == {"m": 2}

    async def test_load_active_executions_datetime_timestamps(self):
        """PostgreSQL returns datetime objects; ensure they get normalised."""
        dt_started = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        dt_completed = datetime(2025, 1, 1, 12, 5, 0, tzinfo=timezone.utc)
        row = _make_db_row(
            status="running",
            started_at=dt_started,
            completed_at=dt_completed,
        )
        db = _mock_db()
        db.execute.return_value = [row]
        tracker = self._tracker(db)
        await tracker._load_active_executions()
        rec = list(tracker.active_executions.values())[0]
        assert isinstance(rec.started_at, str)
        assert isinstance(rec.completed_at, str)

    async def test_load_active_executions_exception(self):
        db = _mock_db()
        db.execute.side_effect = Exception("db error")
        tracker = self._tracker(db)
        # Should not raise
        await tracker._load_active_executions()
        assert tracker.active_executions == {}

    # --- start_execution ---

    async def test_start_execution(self):
        db = _mock_db()
        tracker = self._tracker(db)
        eid = await tracker.start_execution("p1", "Pipeline", {"x": 1}, total_steps=3)
        assert eid in tracker.active_executions
        rec = tracker.active_executions[eid]
        assert rec.status == ExecutionStatus.RUNNING
        assert rec.total_steps == 3
        assert rec.input_data == {"x": 1}
        db.execute.assert_called_once()

    async def test_start_execution_default_metadata(self):
        tracker = self._tracker()
        eid = await tracker.start_execution("p1", "P", {})
        rec = tracker.active_executions[eid]
        assert rec.metadata == {}

    # --- update_execution_status ---

    async def test_update_execution_status_not_found(self):
        tracker = self._tracker()
        # Should just return without error
        await tracker.update_execution_status("nonexistent", ExecutionStatus.COMPLETED)

    async def test_update_execution_status_completed(self):
        db = _mock_db()
        tracker = self._tracker(db)
        eid = await tracker.start_execution("p1", "P", {}, total_steps=1)
        await tracker.update_execution_status(
            eid,
            ExecutionStatus.COMPLETED,
            completed_steps=1,
            output_data={"result": "ok"},
        )
        # Completed executions are removed from active
        assert eid not in tracker.active_executions

    async def test_update_execution_status_failed(self):
        db = _mock_db()
        tracker = self._tracker(db)
        eid = await tracker.start_execution("p1", "P", {}, total_steps=1)
        await tracker.update_execution_status(
            eid,
            ExecutionStatus.FAILED,
            error_message="boom",
            failed_steps=1,
        )
        # Failed executions stay in active for review
        assert eid in tracker.active_executions
        rec = tracker.active_executions[eid]
        assert rec.error_message == "boom"
        assert rec.completed_at is not None

    async def test_update_execution_status_cancelled(self):
        db = _mock_db()
        tracker = self._tracker(db)
        eid = await tracker.start_execution("p1", "P", {}, total_steps=1)
        await tracker.update_execution_status(eid, ExecutionStatus.CANCELLED)
        assert eid not in tracker.active_executions

    async def test_update_execution_status_completed_zero_steps_raises(self):
        db = _mock_db()
        tracker = self._tracker(db)
        eid = await tracker.start_execution("p1", "P", {}, total_steps=3)
        with pytest.raises(ValueError, match="cannot be marked as COMPLETED"):
            await tracker.update_execution_status(eid, ExecutionStatus.COMPLETED)

    async def test_update_execution_status_with_z_timestamp(self):
        """Ensure Z-suffix timestamps are handled."""
        db = _mock_db()
        tracker = self._tracker(db)
        eid = await tracker.start_execution("p1", "P", {}, total_steps=1)
        # Manually set a Z-suffix started_at
        tracker.active_executions[eid].started_at = "2025-01-01T00:00:00Z"
        await tracker.update_execution_status(eid, ExecutionStatus.COMPLETED, completed_steps=1)
        assert eid not in tracker.active_executions

    # --- start_step_execution ---

    async def test_start_step_execution(self):
        db = _mock_db()
        tracker = self._tracker(db)
        sid = await tracker.start_step_execution(
            "exec-1", "step-1", "Step One", "process", input_data={"i": 1}
        )
        assert isinstance(sid, str)
        db.execute_async.assert_called_once()

    # --- complete_step_execution ---

    async def test_complete_step_execution_not_found(self):
        db = _mock_db()
        db.fetch_one.return_value = None
        tracker = self._tracker(db)
        # Should just return without error
        await tracker.complete_step_execution("nonexistent", StepStatus.COMPLETED)

    async def test_complete_step_execution_success(self):
        step_row = _make_step_row(
            step_execution_id="se-1",
            execution_id="e-1",
            status="running",
            started_at="2025-01-01T00:00:00",
        )
        db = _mock_db()
        db.fetch_one.side_effect = [step_row, {"total": 1, "completed": 1, "failed": 0}]
        tracker = self._tracker(db)
        # Put execution in active so step count update works
        tracker.active_executions["e-1"] = ExecutionRecord(
            execution_id="e-1",
            pipeline_id="p1",
            pipeline_name="P",
            status=ExecutionStatus.RUNNING,
            started_at="2025-01-01T00:00:00",
            total_steps=1,
        )
        await tracker.complete_step_execution(
            "se-1",
            StepStatus.COMPLETED,
            output_data={"out": 1},
            retry_count=2,
        )
        # db.execute is called for update step + update execution
        assert db.execute.call_count >= 1

    async def test_complete_step_execution_with_error(self):
        step_row = _make_step_row(
            step_execution_id="se-2",
            execution_id="e-2",
            started_at="2025-01-01T00:00:00",
        )
        db = _mock_db()
        db.fetch_one.side_effect = [step_row, None]
        tracker = self._tracker(db)
        await tracker.complete_step_execution(
            "se-2", StepStatus.FAILED, error_message="step failed"
        )

    async def test_complete_step_with_z_timestamp(self):
        """Test Z-suffix handling in step timestamps."""
        step_row = _make_step_row(
            step_execution_id="se-z",
            started_at="2025-01-01T00:00:00Z",
        )
        db = _mock_db()
        db.fetch_one.side_effect = [step_row, None]
        tracker = self._tracker(db)
        await tracker.complete_step_execution("se-z", StepStatus.COMPLETED)

    # --- get_execution ---

    async def test_get_execution_from_active(self):
        tracker = self._tracker()
        eid = await tracker.start_execution("p1", "P", {})
        result = await tracker.get_execution(eid)
        assert result is not None
        assert result.execution_id == eid

    async def test_get_execution_from_db(self):
        row = _make_db_row(execution_id="e-db")
        db = _mock_db()
        db.fetch_one.return_value = row
        tracker = self._tracker(db)
        result = await tracker.get_execution("e-db")
        assert result is not None
        assert result.execution_id == "e-db"

    async def test_get_execution_not_found(self):
        db = _mock_db()
        db.fetch_one.return_value = None
        tracker = self._tracker(db)
        result = await tracker.get_execution("nope")
        assert result is None

    async def test_get_execution_datetime_timestamps(self):
        row = _make_db_row(
            execution_id="e-dt",
            started_at=datetime(2025, 1, 1, tzinfo=timezone.utc),
            completed_at=datetime(2025, 1, 1, 0, 5, tzinfo=timezone.utc),
            input_data='{"x":1}',
            output_data='{"y":2}',
            metadata_json='{"z":3}',
        )
        db = _mock_db()
        db.fetch_one.return_value = row
        tracker = self._tracker(db)
        result = await tracker.get_execution("e-dt")
        assert result.input_data == {"x": 1}
        assert result.output_data == {"y": 2}
        assert result.metadata == {"z": 3}

    # --- get_execution_steps ---

    async def test_get_execution_steps_empty(self):
        db = _mock_db()
        db.execute.return_value = []
        tracker = self._tracker(db)
        steps = await tracker.get_execution_steps("e-1")
        assert steps == []

    async def test_get_execution_steps_with_data(self):
        row = _make_step_row(
            input_data='{"i":1}',
            output_data='{"o":2}',
            metadata_json='{"m":3}',
        )
        db = _mock_db()
        db.execute.return_value = [row]
        tracker = self._tracker(db)
        steps = await tracker.get_execution_steps("e-1")
        assert len(steps) == 1
        assert steps[0].input_data == {"i": 1}

    # --- get_recent_executions ---

    async def test_get_recent_executions_no_filter(self):
        row = _make_db_row()
        db = _mock_db()
        db.execute.return_value = [row]
        tracker = self._tracker(db)
        results = await tracker.get_recent_executions(limit=10)
        assert len(results) == 1

    async def test_get_recent_executions_with_pipeline_filter(self):
        row = _make_db_row(pipeline_id="p-filter")
        db = _mock_db()
        db.execute.return_value = [row]
        tracker = self._tracker(db)
        results = await tracker.get_recent_executions(limit=5, pipeline_id="p-filter")
        assert len(results) == 1

    async def test_get_recent_executions_datetime_timestamps(self):
        row = _make_db_row(
            started_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
            completed_at=datetime(2025, 6, 1, 0, 1, tzinfo=timezone.utc),
        )
        db = _mock_db()
        db.execute.return_value = [row]
        tracker = self._tracker(db)
        results = await tracker.get_recent_executions()
        assert isinstance(results[0].started_at, str)

    # --- get_execution_by_id ---

    async def test_get_execution_by_id_found(self):
        row = _make_db_row(execution_id="e-byid")
        db = _mock_db()
        db.fetch_one.return_value = row
        tracker = self._tracker(db)
        result = await tracker.get_execution_by_id("e-byid")
        assert result is not None
        assert result.execution_id == "e-byid"

    async def test_get_execution_by_id_not_found(self):
        db = _mock_db()
        db.fetch_one.return_value = None
        tracker = self._tracker(db)
        result = await tracker.get_execution_by_id("nope")
        assert result is None

    async def test_get_execution_by_id_datetime_timestamps(self):
        row = _make_db_row(
            execution_id="e-byid-dt",
            started_at=datetime(2025, 3, 1, tzinfo=timezone.utc),
            completed_at=datetime(2025, 3, 1, 0, 2, tzinfo=timezone.utc),
        )
        db = _mock_db()
        db.fetch_one.return_value = row
        tracker = self._tracker(db)
        result = await tracker.get_execution_by_id("e-byid-dt")
        assert isinstance(result.started_at, str)

    # --- get_execution_statistics ---

    async def test_get_execution_statistics_with_times(self):
        db = _mock_db()
        db.fetch_one.return_value = {"count": 10}
        db.execute.side_effect = [
            [{"status": "completed", "count": 8}, {"status": "failed", "count": 2}],
            [{"execution_time_ms": 100}, {"execution_time_ms": 200}],
        ]
        tracker = self._tracker(db)
        stats = await tracker.get_execution_statistics()
        assert stats["total_executions"] == 10
        assert stats["by_status"]["completed"] == 8
        assert stats["avg_execution_time_ms"] == 150.0
        assert stats["min_execution_time_ms"] == 100
        assert stats["max_execution_time_ms"] == 200

    async def test_get_execution_statistics_no_times(self):
        db = _mock_db()
        db.fetch_one.return_value = {"count": 0}
        db.execute.side_effect = [[], []]
        tracker = self._tracker(db)
        stats = await tracker.get_execution_statistics()
        assert stats["total_executions"] == 0
        assert "avg_execution_time_ms" not in stats

    async def test_get_execution_statistics_total_none(self):
        db = _mock_db()
        db.fetch_one.return_value = None
        db.execute.side_effect = [[], []]
        tracker = self._tracker(db)
        stats = await tracker.get_execution_statistics()
        assert stats["total_executions"] == 0

    # --- WebSocket ---

    def test_add_remove_websocket(self):
        tracker = self._tracker()
        ws = MagicMock()
        tracker.add_websocket_connection(ws)
        assert ws in tracker.websocket_connections
        tracker.remove_websocket_connection(ws)
        assert ws not in tracker.websocket_connections

    def test_remove_websocket_not_present(self):
        tracker = self._tracker()
        ws = MagicMock()
        # Should not raise
        tracker.remove_websocket_connection(ws)

    async def test_broadcast_message_no_connections(self):
        tracker = self._tracker()
        # Should just return
        await tracker._broadcast_message({"type": "test"})

    async def test_broadcast_message_with_connections(self):
        tracker = self._tracker()
        ws = AsyncMock()
        tracker.add_websocket_connection(ws)
        await tracker._broadcast_message({"type": "test"})
        ws.send_text.assert_called_once()

    async def test_broadcast_message_disconnected(self):
        tracker = self._tracker()
        ws = AsyncMock()
        ws.send_text.side_effect = Exception("disconnected")
        tracker.add_websocket_connection(ws)
        await tracker._broadcast_message({"type": "test"})
        assert ws not in tracker.websocket_connections

    # --- _safe_json_dumps ---

    def test_safe_json_dumps_none(self):
        tracker = self._tracker()
        assert tracker._safe_json_dumps(None) is None

    def test_safe_json_dumps_valid(self):
        tracker = self._tracker()
        result = tracker._safe_json_dumps({"a": 1})
        assert json.loads(result) == {"a": 1}

    def test_safe_json_dumps_not_serialisable(self):
        tracker = self._tracker()
        result = tracker._safe_json_dumps(object())
        parsed = json.loads(result)
        assert "_serialization_error" in parsed

    # --- _insert_execution result logging ---

    async def test_insert_execution_with_success_attr(self):
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.success = True
        mock_result.error = None
        db.execute.return_value = mock_result
        tracker = self._tracker(db)
        rec = ExecutionRecord(
            execution_id="e-ins",
            pipeline_id="p1",
            pipeline_name="P",
            status=ExecutionStatus.RUNNING,
            started_at="2025-01-01T00:00:00",
            metadata={"k": "v"},
        )
        await tracker._insert_execution(rec)
        db.execute.assert_called_once()

    async def test_insert_execution_with_error(self):
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "insert failed"
        db.execute.return_value = mock_result
        tracker = self._tracker(db)
        rec = ExecutionRecord(
            execution_id="e-ins-err",
            pipeline_id="p1",
            pipeline_name="P",
            status=ExecutionStatus.RUNNING,
            started_at="2025-01-01T00:00:00",
        )
        await tracker._insert_execution(rec)

    # --- _update_execution result logging ---

    async def test_update_execution_with_error(self):
        db = _mock_db()
        mock_result = MagicMock()
        mock_result.success = False
        mock_result.error = "update failed"
        db.execute.return_value = mock_result
        tracker = self._tracker(db)
        rec = ExecutionRecord(
            execution_id="e-upd",
            pipeline_id="p1",
            pipeline_name="P",
            status=ExecutionStatus.RUNNING,
            started_at="2025-01-01T00:00:00",
            metadata={"k": "v"},
        )
        await tracker._update_execution(rec)

    # --- _get_step_execution with various timestamp formats ---

    async def test_get_step_execution_with_datetime_object(self):
        step_row = _make_step_row(
            started_at=datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            completed_at=datetime(2025, 1, 1, 12, 5, 0, tzinfo=timezone.utc),
            input_data='{"a":1}',
            output_data='{"b":2}',
            metadata_json='{"c":3}',
        )
        db = _mock_db()
        db.fetch_one.return_value = step_row
        tracker = self._tracker(db)
        result = await tracker._get_step_execution("se-dt")
        assert result is not None
        assert isinstance(result.started_at, str)
        assert result.input_data == {"a": 1}

    async def test_get_step_execution_with_z_string(self):
        step_row = _make_step_row(
            started_at="2025-01-01T00:00:00Z",
            completed_at="2025-01-01T00:05:00Z",
        )
        db = _mock_db()
        db.fetch_one.return_value = step_row
        tracker = self._tracker(db)
        result = await tracker._get_step_execution("se-z")
        assert result is not None
        assert "Z" not in result.started_at

    async def test_get_step_execution_with_unparseable_string(self):
        step_row = _make_step_row(
            started_at="not-a-date",
            completed_at=None,
        )
        db = _mock_db()
        db.fetch_one.return_value = step_row
        tracker = self._tracker(db)
        result = await tracker._get_step_execution("se-bad")
        assert result is not None

    async def test_get_step_execution_none_timestamps(self):
        step_row = _make_step_row(started_at=None, completed_at=None)
        db = _mock_db()
        db.fetch_one.return_value = step_row
        tracker = self._tracker(db)
        result = await tracker._get_step_execution("se-none")
        assert result is not None
        assert result.started_at is None

    # --- _update_execution_step_counts ---

    async def test_update_execution_step_counts_no_result(self):
        db = _mock_db()
        db.fetch_one.return_value = None
        tracker = self._tracker(db)
        await tracker._update_execution_step_counts("nonexistent")

    async def test_update_execution_step_counts_not_active(self):
        db = _mock_db()
        db.fetch_one.return_value = {"total": 1, "completed": 1, "failed": 0}
        tracker = self._tracker(db)
        # execution_id not in active_executions -> skip update
        await tracker._update_execution_step_counts("not-active")

    # --- _broadcast_execution_update / _broadcast_step_update ---

    async def test_broadcast_execution_update(self):
        tracker = self._tracker()
        ws = AsyncMock()
        tracker.add_websocket_connection(ws)
        rec = ExecutionRecord(
            execution_id="e-bc",
            pipeline_id="p1",
            pipeline_name="P",
            status=ExecutionStatus.RUNNING,
            started_at="2025-01-01T00:00:00",
        )
        await tracker._broadcast_execution_update(rec)
        ws.send_text.assert_called_once()
        msg = json.loads(ws.send_text.call_args[0][0])
        assert msg["type"] == "execution_update"

    async def test_broadcast_step_update(self):
        tracker = self._tracker()
        ws = AsyncMock()
        tracker.add_websocket_connection(ws)
        step_rec = StepExecutionRecord(
            step_execution_id="se-bc",
            execution_id="e-1",
            step_id="s1",
            step_name="Step",
            step_type="process",
            status=StepStatus.RUNNING,
            started_at="2025-01-01T00:00:00",
        )
        await tracker._broadcast_step_update(step_rec)
        msg = json.loads(ws.send_text.call_args[0][0])
        assert msg["type"] == "step_update"


# ===================================================================
# Global tracker functions
# ===================================================================

class TestGlobalTracker:
    async def test_get_execution_tracker_not_initialised(self):
        import ia_modules.pipeline.execution_tracker as mod
        original = mod.execution_tracker
        try:
            mod.execution_tracker = None
            with pytest.raises(RuntimeError, match="not initialized"):
                get_execution_tracker()
        finally:
            mod.execution_tracker = original

    async def test_initialize_execution_tracker(self):
        import ia_modules.pipeline.execution_tracker as mod
        original = mod.execution_tracker
        try:
            db = _mock_db()
            tracker = await initialize_execution_tracker(db)
            assert isinstance(tracker, ExecutionTracker)
            assert mod.execution_tracker is tracker
        finally:
            mod.execution_tracker = original

    async def test_get_execution_tracker_after_init(self):
        import ia_modules.pipeline.execution_tracker as mod
        original = mod.execution_tracker
        try:
            db = _mock_db()
            await initialize_execution_tracker(db)
            tracker = get_execution_tracker()
            assert isinstance(tracker, ExecutionTracker)
        finally:
            mod.execution_tracker = original


# ===================================================================
# Enum tests
# ===================================================================

class TestEnums:
    def test_execution_status_values(self):
        assert ExecutionStatus.PENDING.value == "pending"
        assert ExecutionStatus.WAITING_FOR_HUMAN.value == "waiting_for_human"

    def test_step_status_values(self):
        assert StepStatus.SKIPPED.value == "skipped"
        assert StepStatus.FAILED.value == "failed"


# ===================================================================
# IterativeRefinementStep tests
# ===================================================================

class TestIterativeRefinementStep:
    async def test_first_iteration(self):
        step = IterativeRefinementStep("refine", {"max_iterations": 3, "prompt": "Improve"})
        result = await step.run({"current_result": "draft text"})
        assert result["status"] == "human_input_required"
        assert result["iteration"] == 1
        assert result["max_iterations"] == 3
        assert "ui_schema" in result
        assert result["ui_schema"]["fields"][0]["default"] == "draft text"

    async def test_max_iterations_exceeded(self):
        step = IterativeRefinementStep("refine", {"max_iterations": 2})
        result = await step.run({
            "current_result": "final",
            "iteration": 3,
            "refinement_history": [{"iteration": 1}, {"iteration": 2}],
        })
        assert result["status"] == "refinement_complete"
        assert result["final_result"] == "final"
        assert result["iterations_completed"] == 2

    async def test_default_config(self):
        step = IterativeRefinementStep("refine", {})
        result = await step.run({})
        assert result["status"] == "human_input_required"
        assert result["max_iterations"] == 3
        assert "Please refine the result" in result["prompt"]

    async def test_last_iteration_checkbox_default(self):
        step = IterativeRefinementStep("refine", {"max_iterations": 2})
        result = await step.run({"iteration": 2})
        # At last iteration, continue checkbox should default False
        checkbox = result["ui_schema"]["fields"][2]
        assert checkbox["default"] is False

    async def test_mid_iteration_checkbox_default(self):
        step = IterativeRefinementStep("refine", {"max_iterations": 5})
        result = await step.run({"iteration": 2})
        checkbox = result["ui_schema"]["fields"][2]
        assert checkbox["default"] is True


class TestProcessRefinementResponseStep:
    async def test_continue_refining(self):
        step = ProcessRefinementResponseStep("process", {})
        result = await step.run({
            "refined_result": "improved text",
            "refinement_notes": "fixed typos",
            "continue_refining": True,
            "iteration": 1,
            "refinement_history": [],
            "max_iterations": 3,
        })
        assert result["status"] == "continue_refinement"
        assert result["iteration"] == 2
        assert result["current_result"] == "improved text"
        assert len(result["refinement_history"]) == 1

    async def test_stop_refining(self):
        step = ProcessRefinementResponseStep("process", {})
        result = await step.run({
            "refined_result": "final text",
            "continue_refining": False,
            "iteration": 2,
            "refinement_history": [{"iteration": 1}],
            "max_iterations": 3,
        })
        assert result["status"] == "refinement_complete"
        assert result["final_result"] == "final text"
        assert result["iterations_completed"] == 2

    async def test_stop_at_max_iterations(self):
        step = ProcessRefinementResponseStep("process", {})
        result = await step.run({
            "refined_result": "done",
            "continue_refining": True,
            "iteration": 3,
            "max_iterations": 3,
        })
        assert result["status"] == "refinement_complete"

    async def test_defaults(self):
        step = ProcessRefinementResponseStep("process", {})
        result = await step.run({})
        # continue_refining defaults False, so should complete
        assert result["status"] == "refinement_complete"
        assert result["iterations_completed"] == 1


# ===================================================================
# runner.py tests
# ===================================================================

class TestLoadStepClass:
    def test_load_step_class_success(self):
        cls = load_step_class("ia_modules.pipeline.core", "Step")
        from ia_modules.pipeline.core import Step
        assert cls is Step

    def test_load_step_class_import_error(self):
        with pytest.raises(ImportError, match="Cannot import module"):
            load_step_class("nonexistent.module", "Foo")

    def test_load_step_class_attribute_error(self):
        with pytest.raises(AttributeError, match="has no class"):
            load_step_class("ia_modules.pipeline.core", "NonexistentClass")


class TestLoadStepClassAsync:
    async def test_without_db_provider(self):
        cls = await load_step_class_async("ia_modules.pipeline.core", "Step")
        from ia_modules.pipeline.core import Step
        assert cls is Step

    async def test_with_db_provider(self):
        mock_loader = AsyncMock()
        mock_loader.load_step_class = AsyncMock(return_value="MockClass")
        with patch("ia_modules.pipeline.db_step_loader.DatabaseStepLoader", return_value=mock_loader):
            result = await load_step_class_async(
                "some.module", "SomeClass", db_provider=MagicMock(), pipeline_id="p1"
            )
        assert result == "MockClass"


class TestCreateStepFromJson:
    def test_basic(self):
        step_def = {
            "module": "ia_modules.pipeline.iterative_refinement",
            "step_class": "IterativeRefinementStep",
            "id": "my-step",
            "config": {"max_iterations": 5},
        }
        step = create_step_from_json(step_def)
        assert step.name == "my-step"
        assert step.config["max_iterations"] == 5

    def test_with_context(self):
        step_def = {
            "module": "ia_modules.pipeline.iterative_refinement",
            "step_class": "IterativeRefinementStep",
            "id": "step-ctx",
            "config": {"prompt": "{{ parameters.my_prompt }}"},
        }
        context = {"parameters": {"my_prompt": "hello"}}
        step = create_step_from_json(step_def, context)
        assert step.config["prompt"] == "hello"

    def test_fallback_name(self):
        step_def = {
            "module": "ia_modules.pipeline.iterative_refinement",
            "step_class": "IterativeRefinementStep",
            "name": "fallback-name",
            "config": {},
        }
        step = create_step_from_json(step_def)
        assert step.name == "fallback-name"

    def test_default_name(self):
        step_def = {
            "module": "ia_modules.pipeline.iterative_refinement",
            "step_class": "IterativeRefinementStep",
            "config": {},
        }
        step = create_step_from_json(step_def)
        assert step.name == "Unknown"

    def test_class_key_fallback(self):
        step_def = {
            "module": "ia_modules.pipeline.iterative_refinement",
            "class": "IterativeRefinementStep",
            "id": "cls-step",
            "config": {},
        }
        step = create_step_from_json(step_def)
        assert step.name == "cls-step"


class TestCreateStepFromJsonAsync:
    async def test_basic(self):
        step_def = {
            "module": "ia_modules.pipeline.iterative_refinement",
            "step_class": "IterativeRefinementStep",
            "id": "async-step",
            "config": {"max_iterations": 2},
        }
        step = await create_step_from_json_async(step_def)
        assert step.name == "async-step"

    async def test_with_context(self):
        step_def = {
            "module": "ia_modules.pipeline.iterative_refinement",
            "step_class": "IterativeRefinementStep",
            "id": "step-async-ctx",
            "config": {"prompt": "{{ parameters.val }}"},
        }
        context = {"parameters": {"val": "world"}}
        step = await create_step_from_json_async(step_def, context)
        assert step.config["prompt"] == "world"

    async def test_with_db_provider(self):
        mock_db_provider = MagicMock()
        mock_loader = AsyncMock()
        mock_loader.load_step_class = AsyncMock(return_value=IterativeRefinementStep)
        with patch("ia_modules.pipeline.db_step_loader.DatabaseStepLoader", return_value=mock_loader):
            step_def = {
                "module": "some.module",
                "step_class": "SomeStep",
                "id": "db-step",
                "config": {},
            }
            step = await create_step_from_json_async(
                step_def, db_provider=mock_db_provider, pipeline_id="p1"
            )
            assert step.name == "db-step"


class TestCreatePipelineFromJson:
    def test_no_services_raises(self):
        config = {
            "name": "Test",
            "steps": [],
        }
        with pytest.raises(ValueError, match="ServiceRegistry is required"):
            create_pipeline_from_json(config)

    def test_basic_pipeline(self):
        config = {
            "name": "Test Pipeline",
            "steps": [
                {
                    "module": "ia_modules.pipeline.iterative_refinement",
                    "step_class": "IterativeRefinementStep",
                    "id": "s1",
                    "config": {},
                }
            ],
        }
        from ia_modules.pipeline.services import ServiceRegistry
        services = ServiceRegistry()
        pipeline = create_pipeline_from_json(config, services)
        assert pipeline.name == "Test Pipeline"

    def test_with_flow(self):
        config = {
            "name": "Flow Pipeline",
            "steps": [
                {
                    "module": "ia_modules.pipeline.iterative_refinement",
                    "step_class": "IterativeRefinementStep",
                    "id": "s1",
                    "config": {},
                }
            ],
            "flow": {"start": "s1"},
            "parameters": {"p1": "string"},
        }
        from ia_modules.pipeline.services import ServiceRegistry
        services = ServiceRegistry()
        pipeline = create_pipeline_from_json(config, services)
        assert pipeline.name == "Flow Pipeline"

    def test_with_input_data(self):
        config = {
            "name": "Param Pipeline",
            "steps": [
                {
                    "module": "ia_modules.pipeline.iterative_refinement",
                    "step_class": "IterativeRefinementStep",
                    "id": "s1",
                    "config": {"prompt": "{{ parameters.msg }}"},
                }
            ],
        }
        from ia_modules.pipeline.services import ServiceRegistry
        services = ServiceRegistry()
        pipeline = create_pipeline_from_json(config, services, input_data={"msg": "hi"})
        # The step config should have resolved the parameter
        assert pipeline.steps[0].config["prompt"] == "hi"

    def test_with_loop_config(self):
        config = {
            "name": "Loop Pipeline",
            "steps": [
                {
                    "module": "ia_modules.pipeline.iterative_refinement",
                    "step_class": "IterativeRefinementStep",
                    "id": "s1",
                    "config": {},
                }
            ],
            "loop_config": {"max_loops": 5},
        }
        from ia_modules.pipeline.services import ServiceRegistry
        services = ServiceRegistry()
        pipeline = create_pipeline_from_json(config, services)
        assert pipeline.name == "Loop Pipeline"

    def test_with_checkpointer_service(self):
        config = {
            "name": "CP Pipeline",
            "steps": [
                {
                    "module": "ia_modules.pipeline.iterative_refinement",
                    "step_class": "IterativeRefinementStep",
                    "id": "s1",
                    "config": {},
                }
            ],
        }
        from ia_modules.pipeline.services import ServiceRegistry
        services = ServiceRegistry()
        mock_cp = MagicMock()
        services.register("checkpointer", mock_cp)
        pipeline = create_pipeline_from_json(config, services)
        assert pipeline.name == "CP Pipeline"


class TestRunPipelineFromJson:
    def _write_config(self, tmp_path):
        config = {
            "name": "Test Pipeline",
            "steps": [
                {
                    "module": "ia_modules.pipeline.iterative_refinement",
                    "step_class": "IterativeRefinementStep",
                    "id": "s1",
                    "config": {"max_iterations": 1},
                }
            ],
        }
        pipeline_file = tmp_path / "pipeline.json"
        pipeline_file.write_text(json.dumps(config))
        return str(pipeline_file)

    async def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            await run_pipeline_from_json("/nonexistent/pipeline.json")

    async def test_successful_run(self, tmp_path):
        pf = self._write_config(tmp_path)
        from ia_modules.pipeline.services import ServiceRegistry
        services = ServiceRegistry()
        with patch("ia_modules.pipeline.core.Pipeline.run", new_callable=AsyncMock, return_value={"ok": True}):
            result = await run_pipeline_from_json(
                pf, input_data={"current_result": "text", "iteration": 2}, services=services,
            )
        assert result == {"ok": True}

    async def test_with_working_directory(self, tmp_path):
        pf = self._write_config(tmp_path)
        from ia_modules.pipeline.services import ServiceRegistry
        services = ServiceRegistry()
        with patch("ia_modules.pipeline.core.Pipeline.run", new_callable=AsyncMock, return_value={"ok": True}):
            result = await run_pipeline_from_json(
                pf, input_data={"iteration": 2, "current_result": "x"},
                services=services, working_directory=str(tmp_path),
            )
        assert result == {"ok": True}

    async def test_with_legacy_params(self, tmp_path):
        pf = self._write_config(tmp_path)
        ws_manager = MagicMock()
        with patch("ia_modules.pipeline.core.Pipeline.run", new_callable=AsyncMock, return_value={"legacy": True}):
            result = await run_pipeline_from_json(
                pf, input_data={"iteration": 2, "current_result": "x"},
                websocket_manager=ws_manager, user_id=42, execution_id="exec-legacy",
            )
        assert result == {"legacy": True}

    async def test_none_input_data(self, tmp_path):
        pf = self._write_config(tmp_path)
        from ia_modules.pipeline.services import ServiceRegistry
        services = ServiceRegistry()
        with patch("ia_modules.pipeline.core.Pipeline.run", new_callable=AsyncMock, return_value={"empty": True}):
            result = await run_pipeline_from_json(pf, input_data=None, services=services)
        assert result == {"empty": True}
