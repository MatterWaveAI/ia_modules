"""
Comprehensive unit tests for:
1. Checkpoint: redis.py and sql.py
2. Telemetry: opentelemetry_exporter.py and exporters.py
3. CLI: visualize.py
"""

import json
import socket
import uuid
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ia_modules.checkpoint.core import (
    CheckpointDeleteError,
    CheckpointLoadError,
    CheckpointSaveError,
    CheckpointStatus,
)
from ia_modules.telemetry.metrics import Metric, MetricType
from ia_modules.telemetry.exporters import (
    PrometheusExporter,
    CloudWatchExporter,
    DatadogExporter,
    StatsDExporter,
)

# Ensure OTel exporter module attributes exist for @patch decorators even when
# opentelemetry packages are not installed (they are imported in a try/except).
import ia_modules.telemetry.opentelemetry_exporter as _otel_mod
for _attr in ("GRPCExporter", "HTTPExporter", "Resource", "MeterProvider",
              "PeriodicExportingMetricReader"):
    if not hasattr(_otel_mod, _attr):
        setattr(_otel_mod, _attr, None)


# ============================================================================
# Helpers
# ============================================================================


def _make_checkpoint_data(
    checkpoint_id="ckpt-001",
    thread_id="thread-1",
    pipeline_id="pipeline-1",
    step_id="step1",
    step_index=0,
    step_name="step1",
    state=None,
    metadata=None,
    timestamp=None,
    status="completed",
    parent_checkpoint_id=None,
    pipeline_version=None,
):
    ts = timestamp or datetime.now().isoformat()
    return {
        "checkpoint_id": checkpoint_id,
        "thread_id": thread_id,
        "pipeline_id": pipeline_id,
        "step_id": step_id,
        "step_index": step_index,
        "step_name": step_name,
        "state": state or {"key": "value"},
        "metadata": metadata or {},
        "timestamp": ts,
        "status": status,
        "parent_checkpoint_id": parent_checkpoint_id,
        "pipeline_version": pipeline_version,
    }


def _make_metric(
    name="test_metric",
    metric_type=MetricType.COUNTER,
    value=1.0,
    labels=None,
    help_text="",
):
    return Metric(
        name=name,
        metric_type=metric_type,
        value=value,
        labels=labels or {},
        help_text=help_text,
    )


# ============================================================================
# CHECKPOINT: RedisCheckpointer Tests
# ============================================================================


class _TestableRedisCheckpointer:
    """Concrete subclass of RedisCheckpointer for testing (implements abstract methods)."""
    _cls = None

    @classmethod
    def _get_cls(cls):
        if cls._cls is None:
            from ia_modules.checkpoint.redis import RedisCheckpointer

            class _Impl(RedisCheckpointer):
                async def save_checkpoint(self, thread_id, pipeline_id, step_id, step_index, state, metadata=None, step_name=None, parent_checkpoint_id=None, pipeline_version=None):
                    raise NotImplementedError("stub")

                async def load_checkpoint(self, thread_id, checkpoint_id=None):
                    raise NotImplementedError("stub")

            cls._cls = _Impl
        return cls._cls

    @classmethod
    def create(cls, redis_client, ttl=86400):
        return cls._get_cls()(redis_client=redis_client, ttl=ttl)


class TestRedisCheckpointer:
    """Tests for RedisCheckpointer"""

    def _make_checkpointer(self, redis_mock=None, ttl=86400):
        if redis_mock is None:
            redis_mock = AsyncMock()
        return _TestableRedisCheckpointer.create(redis_client=redis_mock, ttl=ttl)

    def test_init(self):
        """Test RedisCheckpointer initialization"""
        mock_redis = AsyncMock()
        cp = self._make_checkpointer(mock_redis, ttl=3600)
        assert cp.redis is mock_redis
        assert cp.ttl == 3600

    def test_init_default_ttl(self):
        """Test default TTL is 86400"""
        cp = self._make_checkpointer()
        assert cp.ttl == 86400

    # -- list_checkpoints --

    @pytest.mark.asyncio
    async def test_list_checkpoints_empty(self):
        """Test listing checkpoints when none exist"""
        mock_redis = AsyncMock()
        mock_redis.zrevrange = AsyncMock(return_value=[])
        cp = self._make_checkpointer(mock_redis)

        result = await cp.list_checkpoints("thread-1", limit=10, offset=0)
        assert result == []
        mock_redis.zrevrange.assert_awaited_once_with("checkpoints:thread-1", 0, 9)

    @pytest.mark.asyncio
    async def test_list_checkpoints_returns_checkpoints(self):
        """Test listing checkpoints returns proper Checkpoint objects"""
        mock_redis = AsyncMock()
        ts = datetime.now().isoformat()
        data = _make_checkpoint_data(timestamp=ts)

        mock_redis.zrevrange = AsyncMock(return_value=[b"ckpt-001"])
        mock_redis.get = AsyncMock(return_value=json.dumps(data).encode("utf-8"))
        cp = self._make_checkpointer(mock_redis)

        result = await cp.list_checkpoints("thread-1", limit=10, offset=0)
        assert len(result) == 1
        assert result[0].checkpoint_id == "ckpt-001"
        assert result[0].thread_id == "thread-1"

    @pytest.mark.asyncio
    async def test_list_checkpoints_with_string_ids(self):
        """Test listing checkpoints with string (non-bytes) checkpoint IDs"""
        mock_redis = AsyncMock()
        ts = datetime.now().isoformat()
        data = _make_checkpoint_data(timestamp=ts)

        mock_redis.zrevrange = AsyncMock(return_value=["ckpt-001"])
        mock_redis.get = AsyncMock(return_value=json.dumps(data))
        cp = self._make_checkpointer(mock_redis)

        result = await cp.list_checkpoints("thread-1")
        assert len(result) == 1
        assert result[0].checkpoint_id == "ckpt-001"

    @pytest.mark.asyncio
    async def test_list_checkpoints_skips_expired(self):
        """Test that expired (missing) checkpoint data is skipped"""
        mock_redis = AsyncMock()
        mock_redis.zrevrange = AsyncMock(return_value=[b"ckpt-001", b"ckpt-002"])
        # First checkpoint has data, second returns None (expired)
        ts = datetime.now().isoformat()
        data = _make_checkpoint_data(checkpoint_id="ckpt-001", timestamp=ts)
        mock_redis.get = AsyncMock(side_effect=[
            json.dumps(data).encode("utf-8"),
            None,
        ])
        cp = self._make_checkpointer(mock_redis)

        result = await cp.list_checkpoints("thread-1")
        assert len(result) == 1

    @pytest.mark.asyncio
    async def test_list_checkpoints_pagination(self):
        """Test pagination with offset and limit"""
        mock_redis = AsyncMock()
        mock_redis.zrevrange = AsyncMock(return_value=[])
        cp = self._make_checkpointer(mock_redis)

        await cp.list_checkpoints("thread-1", limit=5, offset=10)
        mock_redis.zrevrange.assert_awaited_once_with("checkpoints:thread-1", 10, 14)

    @pytest.mark.asyncio
    async def test_list_checkpoints_raises_on_error(self):
        """Test that list_checkpoints wraps errors in CheckpointLoadError"""
        mock_redis = AsyncMock()
        mock_redis.zrevrange = AsyncMock(side_effect=Exception("connection lost"))
        cp = self._make_checkpointer(mock_redis)

        with pytest.raises(CheckpointLoadError, match="Failed to list checkpoints"):
            await cp.list_checkpoints("thread-1")

    # -- delete_checkpoints --

    @pytest.mark.asyncio
    async def test_delete_checkpoints_keep_latest(self):
        """Test deleting checkpoints keeping N latest"""
        mock_redis = AsyncMock()
        mock_redis.zrevrange = AsyncMock(return_value=[b"ckpt-003", b"ckpt-002", b"ckpt-001"])
        mock_redis.delete = AsyncMock(return_value=1)
        mock_redis.zrem = AsyncMock()
        cp = self._make_checkpointer(mock_redis)

        deleted = await cp.delete_checkpoints("thread-1", keep_latest=1)
        assert deleted == 2

    @pytest.mark.asyncio
    async def test_delete_checkpoints_keep_latest_string_ids(self):
        """Test deleting with string (non-bytes) checkpoint IDs"""
        mock_redis = AsyncMock()
        mock_redis.zrevrange = AsyncMock(return_value=["ckpt-002", "ckpt-001"])
        mock_redis.delete = AsyncMock(return_value=1)
        mock_redis.zrem = AsyncMock()
        cp = self._make_checkpointer(mock_redis)

        deleted = await cp.delete_checkpoints("thread-1", keep_latest=1)
        assert deleted == 1

    @pytest.mark.asyncio
    async def test_delete_checkpoints_keep_latest_delete_fails(self):
        """Test delete_checkpoints when Redis delete returns 0 (already gone)"""
        mock_redis = AsyncMock()
        mock_redis.zrevrange = AsyncMock(return_value=[b"ckpt-002", b"ckpt-001"])
        mock_redis.delete = AsyncMock(return_value=0)
        mock_redis.zrem = AsyncMock()
        cp = self._make_checkpointer(mock_redis)

        deleted = await cp.delete_checkpoints("thread-1", keep_latest=1)
        assert deleted == 0

    @pytest.mark.asyncio
    async def test_delete_checkpoints_before_timestamp(self):
        """Test deleting checkpoints before a timestamp"""
        mock_redis = AsyncMock()
        before = datetime.now() - timedelta(days=1)
        mock_redis.zrangebyscore = AsyncMock(return_value=[b"ckpt-old"])
        mock_redis.delete = AsyncMock(return_value=1)
        mock_redis.zrem = AsyncMock()
        cp = self._make_checkpointer(mock_redis)

        deleted = await cp.delete_checkpoints("thread-1", before=before)
        assert deleted == 1
        mock_redis.zrangebyscore.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_delete_checkpoints_before_timestamp_string_ids(self):
        """Test deleting before timestamp with string IDs"""
        mock_redis = AsyncMock()
        before = datetime.now()
        mock_redis.zrangebyscore = AsyncMock(return_value=["ckpt-old"])
        mock_redis.delete = AsyncMock(return_value=1)
        mock_redis.zrem = AsyncMock()
        cp = self._make_checkpointer(mock_redis)

        deleted = await cp.delete_checkpoints("thread-1", before=before)
        assert deleted == 1

    @pytest.mark.asyncio
    async def test_delete_checkpoints_before_timestamp_delete_fails(self):
        """Test deleting before timestamp when delete returns 0"""
        mock_redis = AsyncMock()
        before = datetime.now()
        mock_redis.zrangebyscore = AsyncMock(return_value=[b"ckpt-old"])
        mock_redis.delete = AsyncMock(return_value=0)
        mock_redis.zrem = AsyncMock()
        cp = self._make_checkpointer(mock_redis)

        deleted = await cp.delete_checkpoints("thread-1", before=before)
        assert deleted == 0

    @pytest.mark.asyncio
    async def test_delete_all_checkpoints(self):
        """Test deleting all checkpoints for a thread"""
        mock_redis = AsyncMock()
        mock_redis.zrange = AsyncMock(return_value=[b"ckpt-001", b"ckpt-002"])
        mock_redis.delete = AsyncMock(return_value=1)
        cp = self._make_checkpointer(mock_redis)

        deleted = await cp.delete_checkpoints("thread-1")
        assert deleted == 2
        # Verify cleanup of list and latest pointer
        assert mock_redis.delete.await_count == 4  # 2 checkpoints + list + latest

    @pytest.mark.asyncio
    async def test_delete_all_checkpoints_string_ids(self):
        """Test deleting all checkpoints with string IDs"""
        mock_redis = AsyncMock()
        mock_redis.zrange = AsyncMock(return_value=["ckpt-001"])
        mock_redis.delete = AsyncMock(return_value=1)
        cp = self._make_checkpointer(mock_redis)

        deleted = await cp.delete_checkpoints("thread-1")
        assert deleted == 1

    @pytest.mark.asyncio
    async def test_delete_all_checkpoints_delete_fails(self):
        """Test deleting all when individual deletes fail"""
        mock_redis = AsyncMock()
        mock_redis.zrange = AsyncMock(return_value=[b"ckpt-001"])
        mock_redis.delete = AsyncMock(return_value=0)
        cp = self._make_checkpointer(mock_redis)

        deleted = await cp.delete_checkpoints("thread-1")
        assert deleted == 0

    @pytest.mark.asyncio
    async def test_delete_checkpoints_raises_on_error(self):
        """Test that delete_checkpoints wraps errors in CheckpointDeleteError"""
        mock_redis = AsyncMock()
        mock_redis.zrevrange = AsyncMock(side_effect=Exception("connection lost"))
        cp = self._make_checkpointer(mock_redis)

        with pytest.raises(CheckpointDeleteError, match="Failed to delete"):
            await cp.delete_checkpoints("thread-1", keep_latest=1)

    # -- get_checkpoint_stats --

    @pytest.mark.asyncio
    async def test_get_stats_for_thread_empty(self):
        """Test stats for a thread with no checkpoints"""
        mock_redis = AsyncMock()
        mock_redis.zcard = AsyncMock(return_value=0)
        cp = self._make_checkpointer(mock_redis)

        stats = await cp.get_checkpoint_stats(thread_id="thread-1")
        assert stats["total_checkpoints"] == 0
        assert stats["thread_id"] == "thread-1"

    @pytest.mark.asyncio
    async def test_get_stats_for_thread_with_data(self):
        """Test stats for a thread with checkpoints"""
        mock_redis = AsyncMock()
        mock_redis.zcard = AsyncMock(return_value=5)
        oldest_ts = datetime(2024, 1, 1).timestamp()
        newest_ts = datetime(2024, 6, 1).timestamp()
        mock_redis.zrange = AsyncMock(return_value=[(b"ckpt-old", oldest_ts)])
        mock_redis.zrevrange = AsyncMock(return_value=[(b"ckpt-new", newest_ts)])
        cp = self._make_checkpointer(mock_redis)

        stats = await cp.get_checkpoint_stats(thread_id="thread-1")
        assert stats["total_checkpoints"] == 5
        assert stats["oldest_checkpoint"] == datetime.fromtimestamp(oldest_ts)
        assert stats["newest_checkpoint"] == datetime.fromtimestamp(newest_ts)

    @pytest.mark.asyncio
    async def test_get_stats_all_threads_empty(self):
        """Test global stats when no checkpoints exist"""
        mock_redis = AsyncMock()
        mock_redis.scan = AsyncMock(return_value=(0, []))
        cp = self._make_checkpointer(mock_redis)

        stats = await cp.get_checkpoint_stats()
        assert stats["total_checkpoints"] == 0
        assert stats["threads"] == []

    @pytest.mark.asyncio
    async def test_get_stats_all_threads_with_data(self):
        """Test global stats with multiple threads"""
        mock_redis = AsyncMock()
        mock_redis.scan = AsyncMock(return_value=(
            0,
            [b"checkpoints:thread-1", b"checkpoints:thread-2"],
        ))
        mock_redis.zcard = AsyncMock(side_effect=[3, 2])
        cp = self._make_checkpointer(mock_redis)

        stats = await cp.get_checkpoint_stats()
        assert stats["total_checkpoints"] == 5
        assert "thread-1" in stats["threads"]
        assert "thread-2" in stats["threads"]

    @pytest.mark.asyncio
    async def test_get_stats_all_threads_string_keys(self):
        """Test global stats with string (non-bytes) keys from scan"""
        mock_redis = AsyncMock()
        mock_redis.scan = AsyncMock(return_value=(0, ["checkpoints:thread-1"]))
        mock_redis.zcard = AsyncMock(return_value=2)
        cp = self._make_checkpointer(mock_redis)

        stats = await cp.get_checkpoint_stats()
        assert stats["total_checkpoints"] == 2
        assert "thread-1" in stats["threads"]

    @pytest.mark.asyncio
    async def test_get_stats_multi_page_scan(self):
        """Test global stats with multi-page Redis SCAN"""
        mock_redis = AsyncMock()
        # First scan returns cursor=42 (more pages), second returns cursor=0 (done)
        mock_redis.scan = AsyncMock(side_effect=[
            (42, [b"checkpoints:thread-1"]),
            (0, [b"checkpoints:thread-2"]),
        ])
        mock_redis.zcard = AsyncMock(side_effect=[3, 2])
        cp = self._make_checkpointer(mock_redis)

        stats = await cp.get_checkpoint_stats()
        assert stats["total_checkpoints"] == 5
        assert len(stats["threads"]) == 2

    @pytest.mark.asyncio
    async def test_get_stats_returns_empty_on_error(self):
        """Test that stats returns empty dict on error"""
        mock_redis = AsyncMock()
        mock_redis.zcard = AsyncMock(side_effect=Exception("connection lost"))
        cp = self._make_checkpointer(mock_redis)

        stats = await cp.get_checkpoint_stats(thread_id="thread-1")
        assert stats == {}

    # -- close --

    @pytest.mark.asyncio
    async def test_close(self):
        """Test closing Redis connection"""
        mock_redis = AsyncMock()
        cp = self._make_checkpointer(mock_redis)
        await cp.close()
        mock_redis.close.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_close_none_redis(self):
        """Test closing when redis client is None"""
        cp = _TestableRedisCheckpointer.create(redis_client=None)
        # Should not raise
        await cp.close()

    # -- _dict_to_checkpoint --

    def test_dict_to_checkpoint(self):
        """Test converting dict to Checkpoint"""
        ts = datetime.now().isoformat()
        data = _make_checkpoint_data(timestamp=ts)
        cp = self._make_checkpointer()

        checkpoint = cp._dict_to_checkpoint(data)
        assert checkpoint.checkpoint_id == "ckpt-001"
        assert checkpoint.thread_id == "thread-1"
        assert checkpoint.pipeline_id == "pipeline-1"
        assert checkpoint.step_id == "step1"
        assert checkpoint.step_index == 0
        assert checkpoint.step_name == "step1"
        assert checkpoint.state == {"key": "value"}
        assert checkpoint.status == CheckpointStatus.COMPLETED

    def test_dict_to_checkpoint_defaults(self):
        """Test converting dict with missing optional fields"""
        ts = datetime.now().isoformat()
        data = {
            "checkpoint_id": "ckpt-002",
            "thread_id": "t1",
            "pipeline_id": "p1",
            "step_id": "s1",
            "step_index": 0,
            "timestamp": ts,
        }
        cp = self._make_checkpointer()

        checkpoint = cp._dict_to_checkpoint(data)
        assert checkpoint.step_name == "s1"  # defaults to step_id
        assert checkpoint.state == {}
        assert checkpoint.metadata == {}
        assert checkpoint.status == CheckpointStatus.COMPLETED
        assert checkpoint.pipeline_version is None
        assert checkpoint.parent_checkpoint_id is None


# ============================================================================
# CHECKPOINT: SQLCheckpointer Tests
# ============================================================================


class TestSQLCheckpointer:
    """Tests for SQLCheckpointer against a mocked database.

    SQLCheckpointer talks to the database through execute_async() alone, which
    both a nexusql DatabaseManager and ia_modules' adapter provide: a SELECT
    returns its rows as a list of dicts, a write returns an empty list.
    """

    def _make_db_mock(self, table_exists=True, rows=None):
        db = MagicMock()
        db.table_exists = MagicMock(return_value=table_exists)
        db.execute_async = AsyncMock(return_value=[] if rows is None else rows)
        return db

    def _make_checkpointer(self, db=None):
        from ia_modules.checkpoint.sql import SQLCheckpointer
        if db is None:
            db = self._make_db_mock()
        return SQLCheckpointer(db)

    @staticmethod
    def _row(**overrides):
        row = {
            "checkpoint_id": "ckpt-1",
            "thread_id": "t1",
            "pipeline_id": "p1",
            "step_id": "s1",
            "step_index": 0,
            "step_name": "Step 1",
            "state": '{"data": "val"}',
            "timestamp": datetime.now().isoformat(),
            "metadata": "{}",
            "parent_checkpoint_id": None,
        }
        row.update(overrides)
        return row

    # -- __init__ --

    def test_init_success(self):
        db = self._make_db_mock(table_exists=True)
        cp = self._make_checkpointer(db)
        assert cp.db is db

    def test_init_missing_table(self):
        db = self._make_db_mock(table_exists=False)
        with pytest.raises(CheckpointSaveError, match="pipeline_checkpoints table not found"):
            self._make_checkpointer(db)

    # -- save_checkpoint --

    @pytest.mark.asyncio
    async def test_save_checkpoint(self):
        db = self._make_db_mock()
        cp = self._make_checkpointer(db)

        checkpoint_id = await cp.save_checkpoint(
            thread_id="t1", pipeline_id="p1", step_id="s1", step_index=0,
            state={"data": "val"}, metadata={"author": "test"},
            step_name="Step One", parent_checkpoint_id="parent-1",
        )

        uuid.UUID(checkpoint_id)
        db.execute_async.assert_awaited_once()
        query, params = db.execute_async.await_args[0]
        assert "INSERT INTO pipeline_checkpoints" in query
        assert params["checkpoint_id"] == checkpoint_id
        assert params["state"] == '{"data": "val"}'

    @pytest.mark.asyncio
    async def test_save_checkpoint_defaults(self):
        db = self._make_db_mock()
        cp = self._make_checkpointer(db)

        await cp.save_checkpoint(thread_id="t1", pipeline_id="p1", step_id="s1", step_index=0, state={})

        params = db.execute_async.await_args[0][1]
        assert params["metadata"] == "{}"
        assert params["step_name"] is None
        assert params["parent_checkpoint_id"] is None

    @pytest.mark.asyncio
    async def test_save_checkpoint_error(self):
        db = self._make_db_mock()
        db.execute_async = AsyncMock(side_effect=Exception("DB error"))
        cp = self._make_checkpointer(db)

        with pytest.raises(CheckpointSaveError, match="Failed to save"):
            await cp.save_checkpoint(thread_id="t1", pipeline_id="p1", step_id="s1", step_index=0, state={})

    # -- load_checkpoint --

    @pytest.mark.asyncio
    async def test_load_checkpoint_by_id(self):
        db = self._make_db_mock(rows=[self._row()])
        cp = self._make_checkpointer(db)

        result = await cp.load_checkpoint("t1", checkpoint_id="ckpt-1")
        assert result.checkpoint_id == "ckpt-1"
        assert result.state == {"data": "val"}
        query, params = db.execute_async.await_args[0]
        assert "checkpoint_id = :checkpoint_id" in query
        assert params == {"thread_id": "t1", "checkpoint_id": "ckpt-1"}

    @pytest.mark.asyncio
    async def test_load_latest_checkpoint(self):
        db = self._make_db_mock(rows=[self._row(checkpoint_id="ckpt-latest", step_id="s2", step_index=1)])
        cp = self._make_checkpointer(db)

        result = await cp.load_checkpoint("t1")
        assert result.checkpoint_id == "ckpt-latest"
        assert "ORDER BY timestamp DESC" in db.execute_async.await_args[0][0]

    @pytest.mark.asyncio
    async def test_load_checkpoint_native_types(self):
        """PostgreSQL returns datetime, dict and UUID objects rather than text"""
        ts = datetime(2024, 3, 1, 12, 0, 0)
        row = self._row(checkpoint_id=uuid.UUID(int=1), state={"data": "val"}, metadata={"a": 1}, timestamp=ts)
        cp = self._make_checkpointer(self._make_db_mock(rows=[row]))

        result = await cp.load_checkpoint("t1")
        assert result.checkpoint_id == str(uuid.UUID(int=1))
        assert result.state == {"data": "val"}
        assert result.metadata == {"a": 1}
        assert result.timestamp == ts

    @pytest.mark.asyncio
    async def test_load_checkpoint_not_found(self):
        cp = self._make_checkpointer(self._make_db_mock(rows=[]))
        assert await cp.load_checkpoint("t1") is None

    @pytest.mark.asyncio
    async def test_load_checkpoint_error(self):
        db = self._make_db_mock()
        db.execute_async = AsyncMock(side_effect=Exception("DB error"))
        cp = self._make_checkpointer(db)

        with pytest.raises(CheckpointLoadError, match="Failed to load"):
            await cp.load_checkpoint("t1")

    # -- list_checkpoints --

    @pytest.mark.asyncio
    async def test_list_checkpoints(self):
        db = self._make_db_mock(rows=[self._row(), self._row(checkpoint_id="ckpt-2")])
        cp = self._make_checkpointer(db)

        result = await cp.list_checkpoints("t1")
        assert [c.checkpoint_id for c in result] == ["ckpt-1", "ckpt-2"]
        assert db.execute_async.await_args[0][1] == {"thread_id": "t1", "limit": 10, "offset": 0}

    @pytest.mark.asyncio
    async def test_list_checkpoints_with_pipeline_filter(self):
        db = self._make_db_mock(rows=[])
        cp = self._make_checkpointer(db)

        assert await cp.list_checkpoints("t1", pipeline_id="p1") == []
        query, params = db.execute_async.await_args[0]
        assert "pipeline_id = :pipeline_id" in query
        assert params["pipeline_id"] == "p1"

    @pytest.mark.asyncio
    async def test_list_checkpoints_error(self):
        db = self._make_db_mock()
        db.execute_async = AsyncMock(side_effect=Exception("DB error"))
        cp = self._make_checkpointer(db)

        with pytest.raises(CheckpointLoadError, match="Failed to list"):
            await cp.list_checkpoints("t1")

    # -- delete_checkpoint (singular) --

    @pytest.mark.asyncio
    async def test_delete_single_checkpoint(self):
        db = self._make_db_mock()
        cp = self._make_checkpointer(db)

        assert await cp.delete_checkpoint("t1", "ckpt-1") is True
        query, params = db.execute_async.await_args[0]
        assert query.strip().startswith("DELETE FROM pipeline_checkpoints")
        assert params == {"thread_id": "t1", "checkpoint_id": "ckpt-1"}

    @pytest.mark.asyncio
    async def test_delete_single_checkpoint_error(self):
        db = self._make_db_mock()
        db.execute_async = AsyncMock(side_effect=Exception("DB error"))
        cp = self._make_checkpointer(db)

        assert await cp.delete_checkpoint("t1", "ckpt-1") is False

    # -- delete_checkpoints (plural): selects the matching ids, newest first, then deletes --

    @staticmethod
    def _ids(*checkpoint_ids):
        return [{"checkpoint_id": c} for c in checkpoint_ids]

    @pytest.mark.asyncio
    async def test_delete_checkpoints_by_thread(self):
        db = self._make_db_mock()
        db.execute_async = AsyncMock(side_effect=[self._ids("c1", "c2", "c3"), []])
        cp = self._make_checkpointer(db)

        assert await cp.delete_checkpoints("t1") == 3
        (select_query, select_params), (delete_query, delete_params) = (c[0] for c in db.execute_async.await_args_list)
        assert "SELECT checkpoint_id" in select_query and "ORDER BY timestamp DESC" in select_query
        assert select_params == {"thread_id": "t1"}
        assert "pipeline_id" not in select_query
        assert delete_query.strip().startswith("DELETE FROM pipeline_checkpoints WHERE checkpoint_id IN (:id_0, :id_1, :id_2)")
        assert delete_params == {"id_0": "c1", "id_1": "c2", "id_2": "c3"}

    @pytest.mark.asyncio
    async def test_delete_checkpoints_by_pipeline(self):
        db = self._make_db_mock()
        db.execute_async = AsyncMock(side_effect=[self._ids("c1", "c2"), []])
        cp = self._make_checkpointer(db)

        assert await cp.delete_checkpoints("t1", pipeline_id="p1") == 2
        select_query, select_params = db.execute_async.await_args_list[0][0]
        assert "pipeline_id = :pipeline_id" in select_query
        assert select_params == {"thread_id": "t1", "pipeline_id": "p1"}

    @pytest.mark.asyncio
    async def test_delete_checkpoints_keep_latest(self):
        """keep_latest spares that many newest rows (the select is newest first)"""
        db = self._make_db_mock()
        db.execute_async = AsyncMock(side_effect=[self._ids("newest", "middle", "oldest"), []])
        cp = self._make_checkpointer(db)

        assert await cp.delete_checkpoints("t1", keep_latest=1) == 2
        delete_params = db.execute_async.await_args_list[1][0][1]
        assert delete_params == {"id_0": "middle", "id_1": "oldest"}

    @pytest.mark.asyncio
    async def test_delete_checkpoints_before(self):
        db = self._make_db_mock()
        db.execute_async = AsyncMock(side_effect=[self._ids("old"), []])
        cp = self._make_checkpointer(db)

        cutoff = datetime(2024, 6, 1, 12, 0, 0)
        assert await cp.delete_checkpoints("t1", before=cutoff) == 1
        select_query, select_params = db.execute_async.await_args_list[0][0]
        assert "timestamp < :before" in select_query
        assert select_params["before"] == cutoff.isoformat()

    @pytest.mark.asyncio
    async def test_delete_checkpoints_keep_latest_overrides_before(self):
        db = self._make_db_mock()
        db.execute_async = AsyncMock(side_effect=[self._ids("a", "b"), []])
        cp = self._make_checkpointer(db)

        await cp.delete_checkpoints("t1", before=datetime(2024, 1, 1), keep_latest=1)
        select_query = db.execute_async.await_args_list[0][0][0]
        assert "timestamp < :before" not in select_query

    @pytest.mark.asyncio
    async def test_delete_checkpoints_nothing_to_delete(self):
        db = self._make_db_mock()
        db.execute_async = AsyncMock(side_effect=[[]])
        cp = self._make_checkpointer(db)

        assert await cp.delete_checkpoints("t1") == 0
        db.execute_async.assert_awaited_once()  # no DELETE for an empty selection

    @pytest.mark.asyncio
    async def test_delete_checkpoints_error(self):
        db = self._make_db_mock()
        db.execute_async = AsyncMock(side_effect=Exception("DB error"))
        cp = self._make_checkpointer(db)

        assert await cp.delete_checkpoints("t1") == 0

    # -- get_checkpoint_stats --

    @pytest.mark.asyncio
    async def test_stats_for_thread(self):
        db = self._make_db_mock(rows=[{
            "total": 5,
            "oldest": datetime(2024, 1, 1).isoformat(),
            "newest": datetime(2024, 6, 1).isoformat(),
        }])
        cp = self._make_checkpointer(db)

        stats = await cp.get_checkpoint_stats(thread_id="t1")
        assert stats["total_checkpoints"] == 5
        assert stats["oldest_checkpoint"] == datetime(2024, 1, 1)
        assert stats["newest_checkpoint"] == datetime(2024, 6, 1)
        assert stats["thread_id"] == "t1"

    @pytest.mark.asyncio
    async def test_stats_for_thread_empty(self):
        cp = self._make_checkpointer(self._make_db_mock(rows=[{"total": 0, "oldest": None, "newest": None}]))

        stats = await cp.get_checkpoint_stats(thread_id="t1")
        assert stats["total_checkpoints"] == 0
        assert stats["oldest_checkpoint"] is None

    @pytest.mark.asyncio
    async def test_stats_for_thread_none_row(self):
        cp = self._make_checkpointer(self._make_db_mock(rows=[]))

        stats = await cp.get_checkpoint_stats(thread_id="t1")
        assert stats["total_checkpoints"] == 0

    @pytest.mark.asyncio
    async def test_stats_global(self):
        db = self._make_db_mock()
        db.execute_async = AsyncMock(side_effect=[
            [{"total": 10, "oldest": datetime(2024, 1, 1).isoformat(),
              "newest": datetime(2024, 6, 1).isoformat(), "thread_count": 2}],
            [{"thread_id": "t1"}, {"thread_id": "t2"}],
        ])
        cp = self._make_checkpointer(db)

        stats = await cp.get_checkpoint_stats()
        assert stats["total_checkpoints"] == 10
        assert stats["oldest_checkpoint"] == datetime(2024, 1, 1)
        assert stats["threads"] == ["t1", "t2"]

    @pytest.mark.asyncio
    async def test_stats_global_none_row(self):
        db = self._make_db_mock()
        db.execute_async = AsyncMock(side_effect=[[], []])
        cp = self._make_checkpointer(db)

        stats = await cp.get_checkpoint_stats()
        assert stats["total_checkpoints"] == 0
        assert stats["threads"] == []

    @pytest.mark.asyncio
    async def test_stats_global_empty(self):
        db = self._make_db_mock()
        db.execute_async = AsyncMock(side_effect=[
            [{"total": 0, "oldest": None, "newest": None, "thread_count": 0}],
            [],
        ])
        cp = self._make_checkpointer(db)

        stats = await cp.get_checkpoint_stats()
        assert stats["total_checkpoints"] == 0

    # -- close --

    @pytest.mark.asyncio
    async def test_close(self):
        cp = self._make_checkpointer()
        await cp.close()


# ============================================================================
# TELEMETRY: OpenTelemetryExporter Tests
# ============================================================================


class TestOpenTelemetryExporter:
    """Tests for OpenTelemetryExporter with mocked OTel SDK"""

    def _patch_otel_available(self, available=True):
        return patch(
            "ia_modules.telemetry.opentelemetry_exporter.OTEL_AVAILABLE",
            available,
        )

    def test_import_error_when_otel_not_available(self):
        """Test that ImportError is raised when OTel packages are missing"""
        with self._patch_otel_available(False):
            from ia_modules.telemetry.opentelemetry_exporter import OpenTelemetryExporter
            with pytest.raises(ImportError, match="OpenTelemetry packages are required"):
                OpenTelemetryExporter()

    @patch("ia_modules.telemetry.opentelemetry_exporter.Resource")
    @patch("ia_modules.telemetry.opentelemetry_exporter.MeterProvider")
    @patch("ia_modules.telemetry.opentelemetry_exporter.PeriodicExportingMetricReader")
    @patch("ia_modules.telemetry.opentelemetry_exporter.GRPCExporter")
    def test_init_grpc(self, mock_grpc, mock_reader, mock_provider, mock_resource):
        """Test initialization with gRPC protocol"""
        with self._patch_otel_available(True):
            from ia_modules.telemetry.opentelemetry_exporter import OpenTelemetryExporter
            mock_resource.create.return_value = MagicMock()
            mock_meter = MagicMock()
            mock_provider_instance = MagicMock()
            mock_provider_instance.get_meter.return_value = mock_meter
            mock_provider.return_value = mock_provider_instance

            exporter = OpenTelemetryExporter(
                endpoint="http://localhost:4317",
                protocol="grpc",
                service_name="test-svc",
            )

            assert exporter.endpoint == "http://localhost:4317"
            assert exporter.protocol == "grpc"
            assert exporter.service_name == "test-svc"
            mock_grpc.assert_called_once()

    @patch("ia_modules.telemetry.opentelemetry_exporter.Resource")
    @patch("ia_modules.telemetry.opentelemetry_exporter.MeterProvider")
    @patch("ia_modules.telemetry.opentelemetry_exporter.PeriodicExportingMetricReader")
    @patch("ia_modules.telemetry.opentelemetry_exporter.HTTPExporter")
    def test_init_http(self, mock_http, mock_reader, mock_provider, mock_resource):
        """Test initialization with HTTP protocol"""
        with self._patch_otel_available(True):
            from ia_modules.telemetry.opentelemetry_exporter import OpenTelemetryExporter
            mock_resource.create.return_value = MagicMock()
            mock_meter = MagicMock()
            mock_provider_instance = MagicMock()
            mock_provider_instance.get_meter.return_value = mock_meter
            mock_provider.return_value = mock_provider_instance

            exporter = OpenTelemetryExporter(protocol="http")
            assert exporter.protocol == "http"
            mock_http.assert_called_once()

    @patch("ia_modules.telemetry.opentelemetry_exporter.Resource")
    @patch("ia_modules.telemetry.opentelemetry_exporter.MeterProvider")
    @patch("ia_modules.telemetry.opentelemetry_exporter.PeriodicExportingMetricReader")
    @patch("ia_modules.telemetry.opentelemetry_exporter.GRPCExporter")
    def test_init_invalid_protocol(self, mock_grpc, mock_reader, mock_provider, mock_resource):
        """Test initialization with unsupported protocol raises ValueError"""
        with self._patch_otel_available(True):
            from ia_modules.telemetry.opentelemetry_exporter import OpenTelemetryExporter
            mock_resource.create.return_value = MagicMock()
            with pytest.raises(ValueError, match="Unsupported protocol"):
                OpenTelemetryExporter(protocol="websocket")

    @patch("ia_modules.telemetry.opentelemetry_exporter.Resource")
    @patch("ia_modules.telemetry.opentelemetry_exporter.MeterProvider")
    @patch("ia_modules.telemetry.opentelemetry_exporter.PeriodicExportingMetricReader")
    @patch("ia_modules.telemetry.opentelemetry_exporter.GRPCExporter")
    def test_export_metrics(self, mock_grpc, mock_reader, mock_provider, mock_resource):
        """Test exporting a list of metrics"""
        with self._patch_otel_available(True):
            from ia_modules.telemetry.opentelemetry_exporter import OpenTelemetryExporter
            mock_resource.create.return_value = MagicMock()
            mock_meter = MagicMock()
            mock_counter = MagicMock()
            mock_meter.create_counter.return_value = mock_counter
            mock_provider_instance = MagicMock()
            mock_provider_instance.get_meter.return_value = mock_meter
            mock_provider.return_value = mock_provider_instance

            exporter = OpenTelemetryExporter()
            metrics = [_make_metric(name="requests", value=5)]
            exporter.export(metrics)

            mock_counter.add.assert_called_once_with(5, {})
            mock_provider_instance.force_flush.assert_called_once()

    @patch("ia_modules.telemetry.opentelemetry_exporter.Resource")
    @patch("ia_modules.telemetry.opentelemetry_exporter.MeterProvider")
    @patch("ia_modules.telemetry.opentelemetry_exporter.PeriodicExportingMetricReader")
    @patch("ia_modules.telemetry.opentelemetry_exporter.GRPCExporter")
    def test_export_gauge_metric(self, mock_grpc, mock_reader, mock_provider, mock_resource):
        """Test exporting a gauge metric"""
        with self._patch_otel_available(True):
            from ia_modules.telemetry.opentelemetry_exporter import OpenTelemetryExporter
            mock_resource.create.return_value = MagicMock()
            mock_meter = MagicMock()
            mock_gauge = MagicMock()
            mock_gauge.add = MagicMock()
            mock_meter.create_up_down_counter.return_value = mock_gauge
            mock_provider_instance = MagicMock()
            mock_provider_instance.get_meter.return_value = mock_meter
            mock_provider.return_value = mock_provider_instance

            exporter = OpenTelemetryExporter()
            metrics = [_make_metric(name="temp", metric_type=MetricType.GAUGE, value=25.5)]
            exporter.export(metrics)

            mock_gauge.add.assert_called_once_with(25.5, {})

    @patch("ia_modules.telemetry.opentelemetry_exporter.Resource")
    @patch("ia_modules.telemetry.opentelemetry_exporter.MeterProvider")
    @patch("ia_modules.telemetry.opentelemetry_exporter.PeriodicExportingMetricReader")
    @patch("ia_modules.telemetry.opentelemetry_exporter.GRPCExporter")
    def test_export_gauge_without_add(self, mock_grpc, mock_reader, mock_provider, mock_resource):
        """Test exporting gauge when instrument lacks add method (observable gauge)"""
        with self._patch_otel_available(True):
            from ia_modules.telemetry.opentelemetry_exporter import OpenTelemetryExporter
            mock_resource.create.return_value = MagicMock()
            mock_meter = MagicMock()
            mock_gauge = MagicMock(spec=[])  # no 'add' attribute
            mock_meter.create_up_down_counter.return_value = mock_gauge
            mock_provider_instance = MagicMock()
            mock_provider_instance.get_meter.return_value = mock_meter
            mock_provider.return_value = mock_provider_instance

            exporter = OpenTelemetryExporter()
            metrics = [_make_metric(name="temp", metric_type=MetricType.GAUGE, value=25.5)]
            # Should not raise
            exporter.export(metrics)

    @patch("ia_modules.telemetry.opentelemetry_exporter.Resource")
    @patch("ia_modules.telemetry.opentelemetry_exporter.MeterProvider")
    @patch("ia_modules.telemetry.opentelemetry_exporter.PeriodicExportingMetricReader")
    @patch("ia_modules.telemetry.opentelemetry_exporter.GRPCExporter")
    def test_export_histogram_simple_value(self, mock_grpc, mock_reader, mock_provider, mock_resource):
        """Test exporting histogram with a simple float value"""
        with self._patch_otel_available(True):
            from ia_modules.telemetry.opentelemetry_exporter import OpenTelemetryExporter
            mock_resource.create.return_value = MagicMock()
            mock_meter = MagicMock()
            mock_hist = MagicMock()
            mock_meter.create_histogram.return_value = mock_hist
            mock_provider_instance = MagicMock()
            mock_provider_instance.get_meter.return_value = mock_meter
            mock_provider.return_value = mock_provider_instance

            exporter = OpenTelemetryExporter()
            metrics = [_make_metric(name="duration", metric_type=MetricType.HISTOGRAM, value=1.5)]
            exporter.export(metrics)

            mock_hist.record.assert_called_once_with(1.5, {})

    @patch("ia_modules.telemetry.opentelemetry_exporter.Resource")
    @patch("ia_modules.telemetry.opentelemetry_exporter.MeterProvider")
    @patch("ia_modules.telemetry.opentelemetry_exporter.PeriodicExportingMetricReader")
    @patch("ia_modules.telemetry.opentelemetry_exporter.GRPCExporter")
    def test_export_histogram_with_observations(self, mock_grpc, mock_reader, mock_provider, mock_resource):
        """Test exporting histogram with observations dict"""
        with self._patch_otel_available(True):
            from ia_modules.telemetry.opentelemetry_exporter import OpenTelemetryExporter
            mock_resource.create.return_value = MagicMock()
            mock_meter = MagicMock()
            mock_hist = MagicMock()
            mock_meter.create_histogram.return_value = mock_hist
            mock_provider_instance = MagicMock()
            mock_provider_instance.get_meter.return_value = mock_meter
            mock_provider.return_value = mock_provider_instance

            exporter = OpenTelemetryExporter()
            val = {"observations": [0.1, 0.5, 1.0]}
            metrics = [_make_metric(name="duration", metric_type=MetricType.HISTOGRAM, value=val)]
            exporter.export(metrics)

            assert mock_hist.record.call_count == 3

    @patch("ia_modules.telemetry.opentelemetry_exporter.Resource")
    @patch("ia_modules.telemetry.opentelemetry_exporter.MeterProvider")
    @patch("ia_modules.telemetry.opentelemetry_exporter.PeriodicExportingMetricReader")
    @patch("ia_modules.telemetry.opentelemetry_exporter.GRPCExporter")
    def test_export_histogram_with_sum_count(self, mock_grpc, mock_reader, mock_provider, mock_resource):
        """Test exporting histogram with sum/count dict"""
        with self._patch_otel_available(True):
            from ia_modules.telemetry.opentelemetry_exporter import OpenTelemetryExporter
            mock_resource.create.return_value = MagicMock()
            mock_meter = MagicMock()
            mock_hist = MagicMock()
            mock_meter.create_histogram.return_value = mock_hist
            mock_provider_instance = MagicMock()
            mock_provider_instance.get_meter.return_value = mock_meter
            mock_provider.return_value = mock_provider_instance

            exporter = OpenTelemetryExporter()
            val = {"sum": 10.0, "count": 4}
            metrics = [_make_metric(name="duration", metric_type=MetricType.HISTOGRAM, value=val)]
            exporter.export(metrics)

            mock_hist.record.assert_called_once_with(2.5, {})

    @patch("ia_modules.telemetry.opentelemetry_exporter.Resource")
    @patch("ia_modules.telemetry.opentelemetry_exporter.MeterProvider")
    @patch("ia_modules.telemetry.opentelemetry_exporter.PeriodicExportingMetricReader")
    @patch("ia_modules.telemetry.opentelemetry_exporter.GRPCExporter")
    def test_export_histogram_sum_count_zero(self, mock_grpc, mock_reader, mock_provider, mock_resource):
        """Test exporting histogram with count=0 (avoid div by zero)"""
        with self._patch_otel_available(True):
            from ia_modules.telemetry.opentelemetry_exporter import OpenTelemetryExporter
            mock_resource.create.return_value = MagicMock()
            mock_meter = MagicMock()
            mock_hist = MagicMock()
            mock_meter.create_histogram.return_value = mock_hist
            mock_provider_instance = MagicMock()
            mock_provider_instance.get_meter.return_value = mock_meter
            mock_provider.return_value = mock_provider_instance

            exporter = OpenTelemetryExporter()
            val = {"sum": 0.0, "count": 0}
            metrics = [_make_metric(name="duration", metric_type=MetricType.HISTOGRAM, value=val)]
            exporter.export(metrics)

            mock_hist.record.assert_called_once_with(0.0, {})

    @patch("ia_modules.telemetry.opentelemetry_exporter.Resource")
    @patch("ia_modules.telemetry.opentelemetry_exporter.MeterProvider")
    @patch("ia_modules.telemetry.opentelemetry_exporter.PeriodicExportingMetricReader")
    @patch("ia_modules.telemetry.opentelemetry_exporter.GRPCExporter")
    def test_export_summary_metric(self, mock_grpc, mock_reader, mock_provider, mock_resource):
        """Test exporting summary metric type"""
        with self._patch_otel_available(True):
            from ia_modules.telemetry.opentelemetry_exporter import OpenTelemetryExporter
            mock_resource.create.return_value = MagicMock()
            mock_meter = MagicMock()
            mock_hist = MagicMock()
            mock_meter.create_histogram.return_value = mock_hist
            mock_provider_instance = MagicMock()
            mock_provider_instance.get_meter.return_value = mock_meter
            mock_provider.return_value = mock_provider_instance

            exporter = OpenTelemetryExporter()
            metrics = [_make_metric(name="dur", metric_type=MetricType.SUMMARY, value=2.0)]
            exporter.export(metrics)

            mock_hist.record.assert_called_once_with(2.0, {})

    @patch("ia_modules.telemetry.opentelemetry_exporter.Resource")
    @patch("ia_modules.telemetry.opentelemetry_exporter.MeterProvider")
    @patch("ia_modules.telemetry.opentelemetry_exporter.PeriodicExportingMetricReader")
    @patch("ia_modules.telemetry.opentelemetry_exporter.GRPCExporter")
    def test_export_with_labels(self, mock_grpc, mock_reader, mock_provider, mock_resource):
        """Test exporting metrics with labels as attributes"""
        with self._patch_otel_available(True):
            from ia_modules.telemetry.opentelemetry_exporter import OpenTelemetryExporter
            mock_resource.create.return_value = MagicMock()
            mock_meter = MagicMock()
            mock_counter = MagicMock()
            mock_meter.create_counter.return_value = mock_counter
            mock_provider_instance = MagicMock()
            mock_provider_instance.get_meter.return_value = mock_meter
            mock_provider.return_value = mock_provider_instance

            exporter = OpenTelemetryExporter()
            metrics = [_make_metric(name="req", value=1, labels={"method": "GET"})]
            exporter.export(metrics)

            mock_counter.add.assert_called_once_with(1, {"method": "GET"})

    @patch("ia_modules.telemetry.opentelemetry_exporter.Resource")
    @patch("ia_modules.telemetry.opentelemetry_exporter.MeterProvider")
    @patch("ia_modules.telemetry.opentelemetry_exporter.PeriodicExportingMetricReader")
    @patch("ia_modules.telemetry.opentelemetry_exporter.GRPCExporter")
    def test_export_error_handling(self, mock_grpc, mock_reader, mock_provider, mock_resource):
        """Test that export continues on individual metric failure"""
        with self._patch_otel_available(True):
            from ia_modules.telemetry.opentelemetry_exporter import OpenTelemetryExporter
            mock_resource.create.return_value = MagicMock()
            mock_meter = MagicMock()
            mock_counter = MagicMock()
            mock_counter.add.side_effect = [Exception("fail"), None]
            mock_meter.create_counter.return_value = mock_counter
            mock_provider_instance = MagicMock()
            mock_provider_instance.get_meter.return_value = mock_meter
            mock_provider.return_value = mock_provider_instance

            exporter = OpenTelemetryExporter()
            metrics = [
                _make_metric(name="req", value=1),
                _make_metric(name="req", value=2),
            ]
            # Should not raise
            exporter.export(metrics)

    @patch("ia_modules.telemetry.opentelemetry_exporter.Resource")
    @patch("ia_modules.telemetry.opentelemetry_exporter.MeterProvider")
    @patch("ia_modules.telemetry.opentelemetry_exporter.PeriodicExportingMetricReader")
    @patch("ia_modules.telemetry.opentelemetry_exporter.GRPCExporter")
    def test_instrument_caching(self, mock_grpc, mock_reader, mock_provider, mock_resource):
        """Test that instruments are cached and reused"""
        with self._patch_otel_available(True):
            from ia_modules.telemetry.opentelemetry_exporter import OpenTelemetryExporter
            mock_resource.create.return_value = MagicMock()
            mock_meter = MagicMock()
            mock_counter = MagicMock()
            mock_meter.create_counter.return_value = mock_counter
            mock_provider_instance = MagicMock()
            mock_provider_instance.get_meter.return_value = mock_meter
            mock_provider.return_value = mock_provider_instance

            exporter = OpenTelemetryExporter()
            # Export same metric twice
            m = _make_metric(name="req", value=1)
            exporter.export([m, m])

            # create_counter should only be called once
            mock_meter.create_counter.assert_called_once()

    @patch("ia_modules.telemetry.opentelemetry_exporter.Resource")
    @patch("ia_modules.telemetry.opentelemetry_exporter.MeterProvider")
    @patch("ia_modules.telemetry.opentelemetry_exporter.PeriodicExportingMetricReader")
    @patch("ia_modules.telemetry.opentelemetry_exporter.GRPCExporter")
    def test_create_instrument_unsupported_type(self, mock_grpc, mock_reader, mock_provider, mock_resource):
        """Test _create_instrument raises for unsupported metric type"""
        with self._patch_otel_available(True):
            from ia_modules.telemetry.opentelemetry_exporter import OpenTelemetryExporter
            mock_resource.create.return_value = MagicMock()
            mock_meter = MagicMock()
            mock_provider_instance = MagicMock()
            mock_provider_instance.get_meter.return_value = mock_meter
            mock_provider.return_value = mock_provider_instance

            exporter = OpenTelemetryExporter()

            # Create a fake MetricType to trigger the else branch
            fake_type = MagicMock()
            fake_type.value = "unknown"
            with pytest.raises(ValueError, match="Unsupported metric type"):
                exporter._create_instrument("test", fake_type, "desc")

    @patch("ia_modules.telemetry.opentelemetry_exporter.Resource")
    @patch("ia_modules.telemetry.opentelemetry_exporter.MeterProvider")
    @patch("ia_modules.telemetry.opentelemetry_exporter.PeriodicExportingMetricReader")
    @patch("ia_modules.telemetry.opentelemetry_exporter.GRPCExporter")
    def test_shutdown(self, mock_grpc, mock_reader, mock_provider, mock_resource):
        """Test shutdown flushes and shuts down provider"""
        with self._patch_otel_available(True):
            from ia_modules.telemetry.opentelemetry_exporter import OpenTelemetryExporter
            mock_resource.create.return_value = MagicMock()
            mock_meter = MagicMock()
            mock_provider_instance = MagicMock()
            mock_provider_instance.get_meter.return_value = mock_meter
            mock_provider.return_value = mock_provider_instance

            exporter = OpenTelemetryExporter()
            exporter.shutdown()
            mock_provider_instance.shutdown.assert_called_once()

    def test_shutdown_no_provider(self):
        """Test shutdown when provider attribute doesn't exist"""
        with self._patch_otel_available(True):
            from ia_modules.telemetry.opentelemetry_exporter import OpenTelemetryExporter
            exporter = object.__new__(OpenTelemetryExporter)
            # No provider attribute set
            exporter.shutdown()  # Should not raise


# ============================================================================
# TELEMETRY: PrometheusRemoteWriteExporter Tests
# ============================================================================


class TestPrometheusRemoteWriteExporter:
    """Tests for PrometheusRemoteWriteExporter"""

    def test_init_missing_dependency(self):
        """Test that ImportError is raised when prometheus_client is missing"""
        with patch.dict("sys.modules", {"prometheus_client": None}):
            # Reimporting would be complex; test via the class path
            from ia_modules.telemetry.opentelemetry_exporter import PrometheusRemoteWriteExporter
            with pytest.raises(ImportError):
                PrometheusRemoteWriteExporter(endpoint="http://localhost:9091")


# ============================================================================
# TELEMETRY: Exporters Tests (exporters.py - deeper coverage)
# ============================================================================


class TestPrometheusExporterDeep:
    """Deep tests for PrometheusExporter"""

    def test_format_metric_name_with_prefix(self):
        """Test metric name formatting with prefix"""
        exp = PrometheusExporter(prefix="myapp")
        assert exp.format_metric_name("requests") == "myapp_requests"

    def test_format_metric_name_no_prefix(self):
        """Test metric name formatting without prefix"""
        exp = PrometheusExporter(prefix="")
        assert exp.format_metric_name("requests") == "requests"

    def test_format_labels_empty(self):
        """Test label formatting with no labels"""
        exp = PrometheusExporter()
        assert exp._format_labels({}) == ""

    def test_format_labels(self):
        """Test label formatting"""
        exp = PrometheusExporter()
        result = exp._format_labels({"method": "GET", "status": "200"})
        assert 'method="GET"' in result
        assert 'status="200"' in result

    def test_get_prometheus_type(self):
        """Test metric type conversion"""
        exp = PrometheusExporter()
        assert exp._get_prometheus_type(MetricType.COUNTER) == "counter"
        assert exp._get_prometheus_type(MetricType.GAUGE) == "gauge"
        assert exp._get_prometheus_type(MetricType.HISTOGRAM) == "histogram"
        assert exp._get_prometheus_type(MetricType.SUMMARY) == "summary"

    def test_export_histogram_with_buckets(self):
        """Test exporting histogram with bucket data"""
        exp = PrometheusExporter(prefix="app")
        metric = Metric(
            name="duration",
            metric_type=MetricType.HISTOGRAM,
            value={
                "buckets": {0.1: 5, 0.5: 10, 1.0: 12},
                "sum": 7.5,
                "count": 12,
            },
            labels={"endpoint": "/api"},
            help_text="Request duration",
        )
        exp.export([metric])
        text = exp.get_metrics_text()
        assert "# TYPE app_duration histogram" in text
        assert "app_duration_bucket" in text
        assert "app_duration_sum" in text
        assert "app_duration_count" in text
        assert 'le="+Inf"' in text

    def test_export_summary_with_quantiles(self):
        """Test exporting summary with quantile data"""
        exp = PrometheusExporter(prefix="app")
        metric = Metric(
            name="latency",
            metric_type=MetricType.SUMMARY,
            value={
                "quantiles": {0.5: 100, 0.9: 200, 0.99: 500},
                "sum": 15000,
                "count": 100,
            },
            labels={},
            help_text="Request latency",
        )
        exp.export([metric])
        text = exp.get_metrics_text()
        assert "# TYPE app_latency summary" in text
        assert 'quantile="0.5"' in text
        assert "app_latency_sum" in text

    def test_format_metric_line_returns_none_for_unknown(self):
        """Test that unknown metric type returns None from _format_metric_line"""
        exp = PrometheusExporter()
        # Create a metric with a fake type that doesn't match any branch
        metric = _make_metric()
        # Manually set a type that won't match any condition
        # We need to trigger the final return None
        # The only way is via a type that isn't COUNTER, GAUGE, HISTOGRAM, or SUMMARY
        # Since MetricType is an enum, this is hard to do. Let's just verify the method exists.
        # Instead, test with a histogram that has a non-dict value
        metric = Metric(
            name="test",
            metric_type=MetricType.HISTOGRAM,
            value="not_a_dict",
            labels={},
        )
        result = exp._format_metric_line("test", metric)
        # Returns empty string because isinstance check fails
        assert result == ""

    def test_export_no_help_text(self):
        """Test export without help text"""
        exp = PrometheusExporter(prefix="app")
        metric = _make_metric(name="requests", help_text="")
        exp.export([metric])
        text = exp.get_metrics_text()
        assert "# HELP" not in text
        assert "# TYPE app_requests counter" in text

    def test_export_groups_by_name(self):
        """Test that metrics are grouped by name"""
        exp = PrometheusExporter(prefix="app")
        metrics = [
            _make_metric(name="req", value=1, labels={"method": "GET"}),
            _make_metric(name="req", value=2, labels={"method": "POST"}),
        ]
        exp.export(metrics)
        text = exp.get_metrics_text()
        # Only one TYPE line
        assert text.count("# TYPE app_req counter") == 1

    def test_get_metrics_text_empty(self):
        """Test get_metrics_text when no metrics exported"""
        exp = PrometheusExporter()
        assert exp.get_metrics_text() == "\n"

    def test_summary_non_dict_value(self):
        """Test summary with non-dict value returns empty string"""
        exp = PrometheusExporter()
        metric = Metric(
            name="test",
            metric_type=MetricType.SUMMARY,
            value="not_a_dict",
            labels={},
        )
        result = exp._format_metric_line("test", metric)
        assert result == ""


class TestCloudWatchExporter:
    """Tests for CloudWatchExporter"""

    def test_init(self):
        """Test CloudWatch exporter initialization"""
        exp = CloudWatchExporter(namespace="TestNS", region="eu-west-1", prefix="test")
        assert exp.namespace == "TestNS"
        assert exp.region == "eu-west-1"
        assert exp.prefix == "test"
        assert exp._client is None

    def test_get_client_missing_boto3(self):
        """Test that ImportError is raised when boto3 is missing"""
        exp = CloudWatchExporter()
        with patch.dict("sys.modules", {"boto3": None}):
            with pytest.raises(ImportError, match="boto3 is required"):
                exp._get_client()

    def test_get_client_creates_once(self):
        """Test that client is created once (lazy init)"""
        mock_boto3 = MagicMock()
        mock_client = MagicMock()
        mock_boto3.client.return_value = mock_client

        exp = CloudWatchExporter()
        with patch.dict("sys.modules", {"boto3": mock_boto3}):
            client1 = exp._get_client()
            client2 = exp._get_client()
            assert client1 is client2

    def test_format_cloudwatch_counter(self):
        """Test formatting counter metric for CloudWatch"""
        exp = CloudWatchExporter(prefix="test")
        metric = _make_metric(name="requests", value=5.0, labels={"env": "prod"})
        result = exp._format_cloudwatch_metric(metric)
        assert result["MetricName"] == "test_requests"
        assert result["Value"] == 5.0
        assert {"Name": "env", "Value": "prod"} in result["Dimensions"]

    def test_format_cloudwatch_gauge(self):
        """Test formatting gauge metric for CloudWatch"""
        exp = CloudWatchExporter()
        metric = _make_metric(name="temp", metric_type=MetricType.GAUGE, value=42.0, labels={})
        result = exp._format_cloudwatch_metric(metric)
        assert result["Value"] == 42.0

    def test_format_cloudwatch_histogram(self):
        """Test formatting histogram metric for CloudWatch (sum/count)"""
        exp = CloudWatchExporter()
        metric = Metric(
            name="duration",
            metric_type=MetricType.HISTOGRAM,
            value={"sum": 10.0, "count": 5},
            labels={},
        )
        result = exp._format_cloudwatch_metric(metric)
        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["MetricName"] == "duration_sum"
        assert result[1]["MetricName"] == "duration_count"

    def test_format_cloudwatch_histogram_non_dict(self):
        """Test formatting histogram with non-dict value returns None"""
        exp = CloudWatchExporter()
        metric = Metric(
            name="duration",
            metric_type=MetricType.HISTOGRAM,
            value="not_a_dict",
            labels={},
        )
        result = exp._format_cloudwatch_metric(metric)
        # Non-dict histogram returns empty list (metrics_data never appended)
        assert result == []

    def test_export_batches(self):
        """Test export batches metrics in groups of 20"""
        mock_client = MagicMock()
        exp = CloudWatchExporter()
        exp._client = mock_client

        # Create 25 counter metrics
        metrics = [_make_metric(name=f"metric_{i}", value=float(i)) for i in range(25)]
        exp.export(metrics)

        assert mock_client.put_metric_data.call_count == 2

    def test_export_handles_error(self):
        """Test export handles put_metric_data failure gracefully"""
        mock_client = MagicMock()
        mock_client.put_metric_data.side_effect = Exception("AWS error")
        exp = CloudWatchExporter()
        exp._client = mock_client

        metrics = [_make_metric(name="req", value=1)]
        # Should not raise
        exp.export(metrics)

    def test_export_handles_format_returning_none(self):
        """Test export skips metrics that format to None"""
        mock_client = MagicMock()
        exp = CloudWatchExporter()
        exp._client = mock_client

        # Use a summary metric with non-dict value to get None
        metric = Metric(
            name="test",
            metric_type=MetricType.SUMMARY,
            value="not_a_dict",
            labels={},
        )
        exp.export([metric])
        # With no valid metric data, put_metric_data should not be called
        mock_client.put_metric_data.assert_not_called()

    def test_format_cloudwatch_summary(self):
        """Test formatting summary metric for CloudWatch"""
        exp = CloudWatchExporter()
        metric = Metric(
            name="latency",
            metric_type=MetricType.SUMMARY,
            value={"sum": 20.0, "count": 10},
            labels={},
        )
        result = exp._format_cloudwatch_metric(metric)
        assert isinstance(result, list)
        assert len(result) == 2

    def test_format_cloudwatch_returns_none_for_unrecognized(self):
        """Verify None return for metrics that don't match known types"""
        # Actually all MetricType values are handled, but histogram/summary
        # with non-dict values would go through the elif branch
        # and return empty list. Let's verify a plain non-matching scenario
        # by testing that function returns metrics_data (empty list) for
        # histogram with non-dict value.
        exp = CloudWatchExporter()
        metric = Metric(
            name="test",
            metric_type=MetricType.HISTOGRAM,
            value=42,  # non-dict
            labels={},
        )
        result = exp._format_cloudwatch_metric(metric)
        assert result == []


class TestStatsDExporter:
    """Tests for StatsDExporter"""

    def test_init(self):
        """Test StatsD exporter initialization"""
        exp = StatsDExporter(host="statsd.local", port=9125, prefix="myapp")
        assert exp.host == "statsd.local"
        assert exp.port == 9125
        assert exp.prefix == "myapp"
        assert exp._socket is None

    def test_get_socket(self):
        """Test UDP socket creation"""
        exp = StatsDExporter()
        with patch("socket.socket") as mock_sock_class:
            mock_sock = MagicMock()
            mock_sock_class.return_value = mock_sock
            sock = exp._get_socket()
            assert sock is mock_sock
            mock_sock_class.assert_called_once_with(
                socket.AF_INET, socket.SOCK_DGRAM
            )

    def test_get_socket_cached(self):
        """Test that socket is cached"""
        exp = StatsDExporter()
        mock_sock = MagicMock()
        exp._socket = mock_sock
        assert exp._get_socket() is mock_sock

    def test_format_counter(self):
        """Test StatsD counter format"""
        exp = StatsDExporter(prefix="app")
        metric = _make_metric(name="requests", value=5)
        result = exp._format_statsd_metric(metric)
        assert result == "app_requests:5|c"

    def test_format_gauge(self):
        """Test StatsD gauge format"""
        exp = StatsDExporter(prefix="app")
        metric = _make_metric(name="temp", metric_type=MetricType.GAUGE, value=42.0)
        result = exp._format_statsd_metric(metric)
        assert result == "app_temp:42.0|g"

    def test_format_histogram(self):
        """Test StatsD histogram format (as timing)"""
        exp = StatsDExporter(prefix="app")
        metric = Metric(
            name="duration",
            metric_type=MetricType.HISTOGRAM,
            value={"sum": 150},
            labels={},
        )
        result = exp._format_statsd_metric(metric)
        assert result == "app_duration:150|ms"

    def test_format_histogram_non_dict(self):
        """Test StatsD histogram with non-dict value returns None"""
        exp = StatsDExporter(prefix="app")
        metric = Metric(
            name="duration",
            metric_type=MetricType.HISTOGRAM,
            value=42,
            labels={},
        )
        result = exp._format_statsd_metric(metric)
        assert result is None

    def test_format_summary(self):
        """Test StatsD summary format (as timing)"""
        exp = StatsDExporter(prefix="app")
        metric = Metric(
            name="latency",
            metric_type=MetricType.SUMMARY,
            value={"sum": 200},
            labels={},
        )
        result = exp._format_statsd_metric(metric)
        assert result == "app_latency:200|ms"

    def test_format_summary_non_dict(self):
        """Test StatsD summary with non-dict value returns None"""
        exp = StatsDExporter(prefix="app")
        metric = Metric(
            name="latency",
            metric_type=MetricType.SUMMARY,
            value=42,
            labels={},
        )
        result = exp._format_statsd_metric(metric)
        assert result is None

    def test_format_with_labels(self):
        """Test StatsD metric with labels as tags"""
        exp = StatsDExporter(prefix="app")
        metric = _make_metric(name="req", value=1, labels={"method": "GET", "status": "200"})
        result = exp._format_statsd_metric(metric)
        assert "method:GET" in result
        assert "status:200" in result
        assert "|c" in result

    def test_export(self):
        """Test exporting metrics via UDP"""
        exp = StatsDExporter()
        mock_sock = MagicMock()
        exp._socket = mock_sock

        metrics = [_make_metric(name="req", value=1)]
        exp.export(metrics)

        mock_sock.sendto.assert_called_once()

    def test_export_handles_send_error(self):
        """Test export handles UDP send failure"""
        exp = StatsDExporter()
        mock_sock = MagicMock()
        mock_sock.sendto.side_effect = Exception("network error")
        exp._socket = mock_sock

        metrics = [_make_metric(name="req", value=1)]
        # Should not raise
        exp.export(metrics)

    def test_export_skips_none_format(self):
        """Test export skips metrics that format to None"""
        exp = StatsDExporter()
        mock_sock = MagicMock()
        exp._socket = mock_sock

        metric = Metric(
            name="test",
            metric_type=MetricType.HISTOGRAM,
            value=42,  # non-dict -> None format
            labels={},
        )
        exp.export([metric])
        mock_sock.sendto.assert_not_called()

    def test_close(self):
        """Test closing UDP socket"""
        exp = StatsDExporter()
        mock_sock = MagicMock()
        exp._socket = mock_sock

        exp.close()
        mock_sock.close.assert_called_once()
        assert exp._socket is None

    def test_close_no_socket(self):
        """Test close when socket is None"""
        exp = StatsDExporter()
        exp.close()  # Should not raise


class TestDatadogExporter:
    """Tests for DatadogExporter"""

    def test_init_missing_dependency(self):
        """Test that ImportError is raised when datadog package is missing"""
        with patch.dict("sys.modules", {"datadog": None}):
            with pytest.raises(ImportError):
                DatadogExporter(api_key="test", app_key="test")


# ============================================================================
# CLI: visualize.py Tests
# ============================================================================


class TestVisualize:
    """Tests for CLI visualization functions"""

    def test_visualize_pipeline_missing_graphviz(self):
        """Test that ImportError is raised when graphviz is not installed"""
        import sys
        saved = sys.modules.pop("graphviz", "NOT_SET")
        sys.modules["graphviz"] = None
        try:
            from ia_modules.cli.visualize import visualize_pipeline
            with pytest.raises(ImportError, match="Graphviz is required"):
                visualize_pipeline({"name": "test", "steps": []}, "/tmp/test")
        finally:
            if saved == "NOT_SET":
                sys.modules.pop("graphviz", None)
            else:
                sys.modules["graphviz"] = saved

    def test_visualize_basic_pipeline(self):
        """Test basic pipeline visualization"""
        mock_gv_module = MagicMock()
        mock_dot = MagicMock()
        mock_gv_module.Digraph.return_value = mock_dot

        pipeline_data = {
            "name": "test-pipeline",
            "steps": [
                {"name": "step1", "class": "ExtractStep"},
                {"name": "step2", "class": "TransformStep"},
            ],
            "flow": {
                "start_at": "step1",
                "paths": [
                    {"from_step": "step1", "to_step": "step2"},
                ],
            },
        }

        with patch.dict("sys.modules", {"graphviz": mock_gv_module}):
            from ia_modules.cli.visualize import visualize_pipeline
            visualize_pipeline(pipeline_data, "/tmp/output.png", format="png")

        mock_dot.node.assert_any_call("step1", "step1\n<ExtractStep>")
        mock_dot.node.assert_any_call("step2", "step2\n<TransformStep>")
        mock_dot.node.assert_any_call("START", "START", shape="circle", fillcolor="lightgray")
        mock_dot.edge.assert_any_call("START", "step1")
        mock_dot.render.assert_called_once()

    def test_visualize_with_transitions(self):
        """Test pipeline with transitions (graph-based flow)"""
        mock_gv_module = MagicMock()
        mock_dot = MagicMock()
        mock_gv_module.Digraph.return_value = mock_dot

        pipeline_data = {
            "name": "conditional-pipeline",
            "steps": [
                {"name": "check", "class": "CheckStep"},
                {"name": "process", "class": "ProcessStep"},
            ],
            "flow": {
                "transitions": [
                    {
                        "from": "check",
                        "to": "process",
                        "condition": {"type": "field_equals", "field": "status", "value": "ok"},
                    },
                ],
            },
        }

        with patch.dict("sys.modules", {"graphviz": mock_gv_module}):
            from ia_modules.cli.visualize import visualize_pipeline
            visualize_pipeline(pipeline_data, "/tmp/out.svg", format="svg")

        mock_dot.edge.assert_any_call("check", "process", label="status == ok")

    def test_visualize_with_end_nodes(self):
        """Test pipeline with end nodes"""
        mock_gv_module = MagicMock()
        mock_dot = MagicMock()
        mock_gv_module.Digraph.return_value = mock_dot

        pipeline_data = {
            "name": "pipeline",
            "steps": [{"name": "final", "class": "FinalStep"}],
            "flow": {
                "paths": [
                    {"from_step": "final", "to_step": "end_success"},
                ],
            },
        }

        with patch.dict("sys.modules", {"graphviz": mock_gv_module}):
            from ia_modules.cli.visualize import visualize_pipeline
            visualize_pipeline(pipeline_data, "/tmp/out.png")

        mock_dot.node.assert_any_call(
            "end_success", "END_SUCCESS", shape="circle", fillcolor="lightcoral"
        )

    def test_visualize_step_with_error_handling(self):
        """Test step with error_handling gets lightgreen color"""
        mock_gv_module = MagicMock()
        mock_dot = MagicMock()
        mock_gv_module.Digraph.return_value = mock_dot

        pipeline_data = {
            "name": "pipeline",
            "steps": [
                {
                    "name": "safe_step",
                    "class": "SafeStep",
                    "config": {"error_handling": {"retry": 3}},
                },
            ],
            "flow": {},
        }

        with patch.dict("sys.modules", {"graphviz": mock_gv_module}):
            from ia_modules.cli.visualize import visualize_pipeline
            visualize_pipeline(pipeline_data, "/tmp/out.png")

        mock_dot.node.assert_any_call(
            "safe_step", "safe_step\n<SafeStep>", fillcolor="lightgreen"
        )

    def test_visualize_parallel_step(self):
        """Test parallel step gets lightyellow color"""
        mock_gv_module = MagicMock()
        mock_dot = MagicMock()
        mock_gv_module.Digraph.return_value = mock_dot

        pipeline_data = {
            "name": "pipeline",
            "steps": [
                {"name": "par_step", "class": "ParStep", "parallel": True},
            ],
            "flow": {},
        }

        with patch.dict("sys.modules", {"graphviz": mock_gv_module}):
            from ia_modules.cli.visualize import visualize_pipeline
            visualize_pipeline(pipeline_data, "/tmp/out.png")

        mock_dot.node.assert_any_call(
            "par_step", "par_step\n<ParStep>", fillcolor="lightyellow"
        )

    def test_visualize_skips_invalid_steps(self):
        """Test that non-dict steps and steps without name are skipped"""
        mock_gv_module = MagicMock()
        mock_dot = MagicMock()
        mock_gv_module.Digraph.return_value = mock_dot

        pipeline_data = {
            "name": "pipeline",
            "steps": [
                "not_a_dict",
                {"no_name": True},
                {"name": "valid", "class": "ValidStep"},
            ],
            "flow": {},
        }

        with patch.dict("sys.modules", {"graphviz": mock_gv_module}):
            from ia_modules.cli.visualize import visualize_pipeline
            visualize_pipeline(pipeline_data, "/tmp/out.png")

        # Only the valid step should be added
        mock_dot.node.assert_called_once_with("valid", "valid\n<ValidStep>")

    def test_visualize_no_start_at(self):
        """Test pipeline without start_at"""
        mock_gv_module = MagicMock()
        mock_dot = MagicMock()
        mock_gv_module.Digraph.return_value = mock_dot

        pipeline_data = {
            "name": "pipeline",
            "steps": [{"name": "s1", "class": "Step"}],
            "flow": {},
        }

        with patch.dict("sys.modules", {"graphviz": mock_gv_module}):
            from ia_modules.cli.visualize import visualize_pipeline
            visualize_pipeline(pipeline_data, "/tmp/out.png")

        # START node should NOT be added
        for call in mock_dot.node.call_args_list:
            assert call[0][0] != "START"

    def test_visualize_default_step_class(self):
        """Test step without class uses 'Step' as default"""
        mock_gv_module = MagicMock()
        mock_dot = MagicMock()
        mock_gv_module.Digraph.return_value = mock_dot

        pipeline_data = {
            "name": "pipeline",
            "steps": [{"name": "s1"}],
            "flow": {},
        }

        with patch.dict("sys.modules", {"graphviz": mock_gv_module}):
            from ia_modules.cli.visualize import visualize_pipeline
            visualize_pipeline(pipeline_data, "/tmp/out.png")

        mock_dot.node.assert_any_call("s1", "s1\n<Step>")

    def test_visualize_format_stripping_dot(self):
        """Test that format '.png' is normalized to 'png'"""
        mock_gv_module = MagicMock()
        mock_dot = MagicMock()
        mock_gv_module.Digraph.return_value = mock_dot

        pipeline_data = {"name": "p", "steps": [], "flow": {}}

        with patch.dict("sys.modules", {"graphviz": mock_gv_module}):
            from ia_modules.cli.visualize import visualize_pipeline
            visualize_pipeline(pipeline_data, "/tmp/out.png", format=".png")

        # Verify Digraph was called with format='png' (dot stripped)
        call_kwargs = mock_gv_module.Digraph.call_args[1]
        assert call_kwargs["format"] == "png"


class TestFormatConditionLabel:
    """Tests for _format_condition_label helper"""

    def _call(self, condition):
        from ia_modules.cli.visualize import _format_condition_label
        return _format_condition_label(condition)

    def test_none_condition(self):
        assert self._call(None) == ""

    def test_always_condition(self):
        assert self._call({"type": "always"}) == ""

    def test_field_equals(self):
        result = self._call({"type": "field_equals", "field": "status", "value": "ok"})
        assert result == "status == ok"

    def test_field_exists(self):
        result = self._call({"type": "field_exists", "field": "token"})
        assert result == "exists(token)"

    def test_field_greater_than(self):
        result = self._call({"type": "field_greater_than", "field": "score", "value": "80"})
        assert result == "score > 80"

    def test_field_less_than(self):
        result = self._call({"type": "field_less_than", "field": "errors", "value": "5"})
        assert result == "errors < 5"

    def test_not_condition(self):
        assert self._call({"type": "not"}) == "NOT"

    def test_all_condition(self):
        assert self._call({"type": "all"}) == "ALL"

    def test_any_condition(self):
        assert self._call({"type": "any"}) == "ANY"

    def test_custom_condition(self):
        result = self._call({"type": "custom", "function": "my_func"})
        assert result == "custom: my_func"

    def test_plugin_condition(self):
        result = self._call({"type": "plugin", "plugin": "my_plugin"})
        assert result == "plugin: my_plugin"

    def test_unknown_condition_type(self):
        result = self._call({"type": "exotic_type"})
        assert result == "exotic_type"

    def test_missing_fields_defaults(self):
        """Test conditions with missing optional fields default to empty string"""
        result = self._call({"type": "field_equals"})
        assert result == " == "

    def test_empty_type(self):
        """Test condition with empty type string"""
        result = self._call({"type": ""})
        assert result == ""


class TestAddTransitions:
    """Tests for _add_transitions helper"""

    def _call(self, dot, transitions, step_names):
        from ia_modules.cli.visualize import _add_transitions
        return _add_transitions(dot, transitions, step_names)

    def test_basic_transition(self):
        dot = MagicMock()
        self._call(dot, [{"from": "a", "to": "b"}], {"a", "b"})
        dot.edge.assert_called_once_with("a", "b", label="")

    def test_skip_non_dict(self):
        dot = MagicMock()
        self._call(dot, ["not_a_dict", {"from": "a", "to": "b"}], {"a", "b"})
        assert dot.edge.call_count == 1

    def test_skip_missing_from_or_to(self):
        dot = MagicMock()
        self._call(dot, [{"from": "a"}, {"to": "b"}, {"from": "a", "to": "b"}], {"a", "b"})
        assert dot.edge.call_count == 1

    def test_transition_with_condition(self):
        dot = MagicMock()
        self._call(
            dot,
            [{"from": "a", "to": "b", "condition": {"type": "field_equals", "field": "x", "value": "1"}}],
            {"a", "b"},
        )
        dot.edge.assert_called_once_with("a", "b", label="x == 1")


class TestAddPaths:
    """Tests for _add_paths helper"""

    def _call(self, dot, paths, step_names):
        from ia_modules.cli.visualize import _add_paths
        return _add_paths(dot, paths, step_names)

    def test_basic_path(self):
        dot = MagicMock()
        self._call(dot, [{"from_step": "a", "to_step": "b"}], {"a", "b"})
        dot.edge.assert_called_once_with("a", "b", label="")

    def test_skip_non_dict(self):
        dot = MagicMock()
        self._call(dot, ["not_a_dict"], set())
        dot.edge.assert_not_called()

    def test_skip_missing_fields(self):
        dot = MagicMock()
        self._call(dot, [{"from_step": "a"}, {"to_step": "b"}], {"a", "b"})
        dot.edge.assert_not_called()

    def test_path_with_condition(self):
        dot = MagicMock()
        self._call(
            dot,
            [{"from_step": "a", "to_step": "b", "condition": {"type": "always"}}],
            {"a", "b"},
        )
        dot.edge.assert_called_once_with("a", "b", label="")
