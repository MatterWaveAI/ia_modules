"""
Comprehensive unit tests for StateManager

Tests all methods and edge cases in agents/state.py to achieve 100% coverage
"""

import pytest
from unittest.mock import Mock, AsyncMock
import asyncio

from ia_modules.agents.state import StateManager


class TestStateManagerInit:
    """Test StateManager initialization"""

    def test_init_minimal(self):
        """Test initialization with minimal parameters"""
        state = StateManager(thread_id="test-123")

        assert state.thread_id == "test-123"
        assert state.checkpointer is None
        assert state._state == {}
        assert state._versions == []
        assert state._lock is not None
        assert state.logger is not None

    def test_init_with_checkpointer(self):
        """Test initialization with checkpointer"""
        mock_checkpointer = Mock()
        state = StateManager(thread_id="test-123", checkpointer=mock_checkpointer)

        assert state.checkpointer == mock_checkpointer

    def test_logger_name_includes_thread_id(self):
        """Test that logger name includes thread ID"""
        state = StateManager(thread_id="user-456")

        assert "user-456" in state.logger.name


class TestStateManagerGetSet:
    """Test basic get/set operations"""

    @pytest.mark.asyncio
    async def test_get_existing_key(self):
        """Test getting existing key"""
        state = StateManager(thread_id="test")
        state._state["key1"] = "value1"

        result = await state.get("key1")

        assert result == "value1"

    @pytest.mark.asyncio
    async def test_get_missing_key_default_none(self):
        """Test getting missing key returns None"""
        state = StateManager(thread_id="test")

        result = await state.get("missing")

        assert result is None

    @pytest.mark.asyncio
    async def test_get_missing_key_with_default(self):
        """Test getting missing key with custom default"""
        state = StateManager(thread_id="test")

        result = await state.get("missing", default="default_value")

        assert result == "default_value"

    @pytest.mark.asyncio
    async def test_set_new_key(self):
        """Test setting new key"""
        state = StateManager(thread_id="test")

        await state.set("key1", "value1")

        assert state._state["key1"] == "value1"

    @pytest.mark.asyncio
    async def test_set_creates_version(self):
        """Test that set creates version snapshot"""
        state = StateManager(thread_id="test")
        state._state["existing"] = "old"

        await state.set("key1", "value1")

        assert len(state._versions) == 1
        assert state._versions[0] == {"existing": "old"}

    @pytest.mark.asyncio
    async def test_set_with_checkpointer(self):
        """Test set persists to checkpointer"""
        mock_checkpointer = Mock()
        mock_checkpointer.save_checkpoint = AsyncMock()
        state = StateManager(thread_id="test", checkpointer=mock_checkpointer)

        await state.set("key1", "value1")

        mock_checkpointer.save_checkpoint.assert_called_once()

    @pytest.mark.asyncio
    async def test_set_multiple_times(self):
        """Test setting multiple values creates multiple versions"""
        state = StateManager(thread_id="test")

        await state.set("key1", "value1")
        await state.set("key2", "value2")
        await state.set("key3", "value3")

        assert len(state._versions) == 3
        assert state._state == {"key1": "value1", "key2": "value2", "key3": "value3"}


class TestStateManagerUpdate:
    """Test batch update operations"""

    @pytest.mark.asyncio
    async def test_update_single_key(self):
        """Test updating single key"""
        state = StateManager(thread_id="test")

        await state.update({"key1": "value1"})

        assert state._state["key1"] == "value1"

    @pytest.mark.asyncio
    async def test_update_multiple_keys(self):
        """Test updating multiple keys atomically"""
        state = StateManager(thread_id="test")

        await state.update({"key1": "value1", "key2": "value2", "key3": "value3"})

        assert state._state == {"key1": "value1", "key2": "value2", "key3": "value3"}

    @pytest.mark.asyncio
    async def test_update_overwrites_existing(self):
        """Test update overwrites existing keys"""
        state = StateManager(thread_id="test")
        state._state["key1"] = "old"

        await state.update({"key1": "new", "key2": "value2"})

        assert state._state["key1"] == "new"

    @pytest.mark.asyncio
    async def test_update_creates_version(self):
        """Test update creates version snapshot"""
        state = StateManager(thread_id="test")
        state._state["existing"] = "old"

        await state.update({"key1": "value1"})

        assert len(state._versions) == 1
        assert state._versions[0] == {"existing": "old"}

    @pytest.mark.asyncio
    async def test_update_with_checkpointer(self):
        """Test update persists to checkpointer"""
        mock_checkpointer = Mock()
        mock_checkpointer.save_checkpoint = AsyncMock()
        state = StateManager(thread_id="test", checkpointer=mock_checkpointer)

        await state.update({"key1": "value1"})

        mock_checkpointer.save_checkpoint.assert_called_once()


class TestStateManagerDelete:
    """Test delete operations"""

    @pytest.mark.asyncio
    async def test_delete_existing_key(self):
        """Test deleting existing key"""
        state = StateManager(thread_id="test")
        state._state["key1"] = "value1"

        result = await state.delete("key1")

        assert result is True
        assert "key1" not in state._state

    @pytest.mark.asyncio
    async def test_delete_missing_key(self):
        """Test deleting missing key returns False"""
        state = StateManager(thread_id="test")

        result = await state.delete("missing")

        assert result is False

    @pytest.mark.asyncio
    async def test_delete_creates_version(self):
        """Test delete creates version snapshot"""
        state = StateManager(thread_id="test")
        state._state["key1"] = "value1"

        await state.delete("key1")

        assert len(state._versions) == 1
        assert state._versions[0] == {"key1": "value1"}

    @pytest.mark.asyncio
    async def test_delete_with_checkpointer(self):
        """Test delete persists to checkpointer"""
        mock_checkpointer = Mock()
        mock_checkpointer.save_checkpoint = AsyncMock()
        state = StateManager(thread_id="test", checkpointer=mock_checkpointer)
        state._state["key1"] = "value1"

        await state.delete("key1")

        mock_checkpointer.save_checkpoint.assert_called_once()


class TestStateManagerClear:
    """Test clear operations"""

    @pytest.mark.asyncio
    async def test_clear_removes_all(self):
        """Test clear removes all state"""
        state = StateManager(thread_id="test")
        state._state = {"key1": "value1", "key2": "value2"}

        await state.clear()

        assert state._state == {}

    @pytest.mark.asyncio
    async def test_clear_empty_state(self):
        """Test clear on empty state"""
        state = StateManager(thread_id="test")

        await state.clear()

        assert state._state == {}

    @pytest.mark.asyncio
    async def test_clear_creates_version(self):
        """Test clear creates version snapshot"""
        state = StateManager(thread_id="test")
        state._state = {"key1": "value1"}

        await state.clear()

        assert len(state._versions) == 1
        assert state._versions[0] == {"key1": "value1"}

    @pytest.mark.asyncio
    async def test_clear_empty_state_no_version(self):
        """Test clear on empty state does not create version"""
        state = StateManager(thread_id="test")

        await state.clear()

        assert len(state._versions) == 0

    @pytest.mark.asyncio
    async def test_clear_with_checkpointer(self):
        """Test clear persists to checkpointer"""
        mock_checkpointer = Mock()
        mock_checkpointer.save_checkpoint = AsyncMock()
        state = StateManager(thread_id="test", checkpointer=mock_checkpointer)
        state._state = {"key1": "value1"}

        await state.clear()

        mock_checkpointer.save_checkpoint.assert_called_once()


class TestStateManagerSnapshot:
    """Test snapshot operations"""

    @pytest.mark.asyncio
    async def test_snapshot_returns_copy(self):
        """Test snapshot returns deep copy"""
        state = StateManager(thread_id="test")
        state._state = {"key1": {"nested": "value"}}

        snapshot = await state.snapshot()

        # Modify snapshot should not affect original
        snapshot["key1"]["nested"] = "modified"
        assert state._state["key1"]["nested"] == "value"

    @pytest.mark.asyncio
    async def test_snapshot_empty_state(self):
        """Test snapshot of empty state"""
        state = StateManager(thread_id="test")

        snapshot = await state.snapshot()

        assert snapshot == {}


class TestStateManagerRollback:
    """Test rollback operations"""

    @pytest.mark.asyncio
    async def test_rollback_one_step(self):
        """Test rollback one version"""
        state = StateManager(thread_id="test")
        await state.set("key1", "value1")
        await state.set("key2", "value2")

        result = await state.rollback(steps=1)

        assert result is True
        assert state._state == {"key1": "value1"}

    @pytest.mark.asyncio
    async def test_rollback_multiple_steps(self):
        """Test rollback multiple versions"""
        state = StateManager(thread_id="test")
        await state.set("key1", "value1")
        await state.set("key2", "value2")
        await state.set("key3", "value3")

        result = await state.rollback(steps=2)

        assert result is True
        assert state._state == {"key1": "value1"}

    @pytest.mark.asyncio
    async def test_rollback_insufficient_history(self):
        """Test rollback with insufficient history"""
        state = StateManager(thread_id="test")
        await state.set("key1", "value1")

        result = await state.rollback(steps=5)

        assert result is False

    @pytest.mark.asyncio
    async def test_rollback_no_history(self):
        """Test rollback with no history"""
        state = StateManager(thread_id="test")

        result = await state.rollback(steps=1)

        assert result is False

    @pytest.mark.asyncio
    async def test_rollback_with_checkpointer(self):
        """Test rollback persists to checkpointer"""
        mock_checkpointer = Mock()
        mock_checkpointer.save_checkpoint = AsyncMock()
        state = StateManager(thread_id="test", checkpointer=mock_checkpointer)
        await state.set("key1", "value1")
        await state.set("key2", "value2")
        mock_checkpointer.save_checkpoint.reset_mock()

        await state.rollback(steps=1)

        mock_checkpointer.save_checkpoint.assert_called_once()

    @pytest.mark.asyncio
    async def test_rollback_removes_versions(self):
        """Test rollback removes rolled-back versions from history"""
        state = StateManager(thread_id="test")
        await state.set("key1", "value1")
        await state.set("key2", "value2")
        await state.set("key3", "value3")

        await state.rollback(steps=2)

        assert len(state._versions) == 1


class TestStateManagerHistory:
    """Test history operations"""

    @pytest.mark.asyncio
    async def test_get_history_default_limit(self):
        """Test get history with default limit"""
        state = StateManager(thread_id="test")
        for i in range(5):
            await state.set(f"key{i}", f"value{i}")

        history = await state.get_history()

        assert len(history) == 5

    @pytest.mark.asyncio
    async def test_get_history_custom_limit(self):
        """Test get history with custom limit"""
        state = StateManager(thread_id="test")
        for i in range(10):
            await state.set(f"key{i}", f"value{i}")

        history = await state.get_history(limit=3)

        assert len(history) == 3

    @pytest.mark.asyncio
    async def test_get_history_most_recent_first(self):
        """Test history is returned most recent first"""
        state = StateManager(thread_id="test")
        await state.set("key1", "value1")
        await state.set("key2", "value2")

        history = await state.get_history()

        # Most recent should be {"key1": "value1"} (before key2 was added)
        assert history[0] == {"key1": "value1"}
        assert history[1] == {}

    @pytest.mark.asyncio
    async def test_get_history_returns_copies(self):
        """Test history returns deep copies"""
        state = StateManager(thread_id="test")
        state._state = {"existing": {"nested": "value"}}
        await state.set("key1", "value1")  # Creates snapshot of existing state

        history = await state.get_history()

        # Modify history should not affect versions
        history[0]["existing"]["nested"] = "modified"
        assert state._versions[0]["existing"]["nested"] == "value"

    @pytest.mark.asyncio
    async def test_get_history_empty(self):
        """Test get history when no history"""
        state = StateManager(thread_id="test")

        history = await state.get_history()

        assert history == []

    def test_version_count(self):
        """Test version count method"""
        state = StateManager(thread_id="test")
        state._versions = [{"a": 1}, {"b": 2}, {"c": 3}]

        count = state.version_count()

        assert count == 3

    def test_version_count_zero(self):
        """Test version count with no versions"""
        state = StateManager(thread_id="test")

        count = state.version_count()

        assert count == 0


class TestStateManagerPersistence:
    """Test checkpointer persistence"""

    @pytest.mark.asyncio
    async def test_persist_saves_checkpoint(self):
        """Test _persist saves checkpoint"""
        mock_checkpointer = Mock()
        mock_checkpointer.save_checkpoint = AsyncMock()
        state = StateManager(thread_id="test-123", checkpointer=mock_checkpointer)
        state._state = {"key1": "value1"}

        await state._persist()

        call_kwargs = mock_checkpointer.save_checkpoint.call_args[1]
        assert call_kwargs["thread_id"] == "test-123"
        assert call_kwargs["pipeline_id"] == "agent_orchestration"
        assert call_kwargs["step_id"] == "state_snapshot"
        assert call_kwargs["state"] == {"key1": "value1"}

    @pytest.mark.asyncio
    async def test_persist_no_checkpointer(self):
        """Test _persist without checkpointer"""
        state = StateManager(thread_id="test")

        # Should not raise error
        await state._persist()

    @pytest.mark.asyncio
    async def test_persist_handles_errors(self):
        """Test _persist handles errors gracefully"""
        mock_checkpointer = Mock()
        mock_checkpointer.save_checkpoint = AsyncMock(side_effect=Exception("DB error"))
        state = StateManager(thread_id="test", checkpointer=mock_checkpointer)

        # Should not raise error
        await state._persist()

    @pytest.mark.asyncio
    async def test_restore_success(self):
        """Test restore from checkpoint"""
        mock_checkpoint = Mock()
        mock_checkpoint.state = {"key1": "restored"}
        mock_checkpoint.checkpoint_id = "cp-123"

        mock_checkpointer = Mock()
        mock_checkpointer.load_checkpoint = AsyncMock(return_value=mock_checkpoint)

        state = StateManager(thread_id="test", checkpointer=mock_checkpointer)

        result = await state.restore_from_checkpoint()

        assert result is True
        assert state._state == {"key1": "restored"}

    @pytest.mark.asyncio
    async def test_restore_with_checkpoint_id(self):
        """Test restore specific checkpoint"""
        mock_checkpoint = Mock()
        mock_checkpoint.state = {"key1": "restored"}
        mock_checkpoint.checkpoint_id = "cp-456"

        mock_checkpointer = Mock()
        mock_checkpointer.load_checkpoint = AsyncMock(return_value=mock_checkpoint)

        state = StateManager(thread_id="test", checkpointer=mock_checkpointer)

        result = await state.restore_from_checkpoint(checkpoint_id="cp-456")

        assert result is True
        mock_checkpointer.load_checkpoint.assert_called_with(
            thread_id="test",
            checkpoint_id="cp-456"
        )

    @pytest.mark.asyncio
    async def test_restore_no_checkpointer(self):
        """Test restore without checkpointer"""
        state = StateManager(thread_id="test")

        result = await state.restore_from_checkpoint()

        assert result is False

    @pytest.mark.asyncio
    async def test_restore_no_checkpoint_found(self):
        """Test restore when no checkpoint exists"""
        mock_checkpointer = Mock()
        mock_checkpointer.load_checkpoint = AsyncMock(return_value=None)

        state = StateManager(thread_id="test", checkpointer=mock_checkpointer)

        result = await state.restore_from_checkpoint()

        assert result is False

    @pytest.mark.asyncio
    async def test_restore_handles_errors(self):
        """Test restore handles errors gracefully"""
        mock_checkpointer = Mock()
        mock_checkpointer.load_checkpoint = AsyncMock(side_effect=Exception("DB error"))

        state = StateManager(thread_id="test", checkpointer=mock_checkpointer)

        result = await state.restore_from_checkpoint()

        assert result is False


class TestStateManagerRepr:
    """Test string representation"""

    def test_repr(self):
        """Test __repr__ method"""
        state = StateManager(thread_id="test-123")
        state._state = {"key1": "value1", "key2": "value2"}
        state._versions = [{}, {"key1": "value1"}]

        repr_str = repr(state)

        assert "test-123" in repr_str
        assert "keys=2" in repr_str
        assert "versions=2" in repr_str


class TestStateManagerConcurrency:
    """Test thread safety and locking"""

    @pytest.mark.asyncio
    async def test_concurrent_reads(self):
        """Test concurrent reads are safe"""
        state = StateManager(thread_id="test")
        state._state = {"key1": "value1"}

        # Multiple concurrent reads
        results = await asyncio.gather(
            state.get("key1"),
            state.get("key1"),
            state.get("key1")
        )

        assert all(r == "value1" for r in results)

    @pytest.mark.asyncio
    async def test_concurrent_writes(self):
        """Test concurrent writes use locking"""
        state = StateManager(thread_id="test")

        # Multiple concurrent writes
        await asyncio.gather(
            state.set("key1", "value1"),
            state.set("key2", "value2"),
            state.set("key3", "value3")
        )

        assert len(state._state) == 3
        # Should have 3 versions (one for each set)
        assert len(state._versions) == 3


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
