"""
Unit tests for state management.

Tests StateManager functionality including versioning and persistence.
"""
import pytest
from ia_modules.agents.state import StateManager
from ia_modules.checkpoint.memory import MemoryCheckpointer


@pytest.mark.asyncio
class TestStateManager:
    """Test StateManager functionality."""

    async def test_state_creation(self):
        """StateManager can be created."""
        state = StateManager(thread_id="test-thread")

        assert state.thread_id == "test-thread"
        assert state.checkpointer is None
        assert state.version_count() == 0

    async def test_get_set(self):
        """State can get and set values."""
        state = StateManager(thread_id="test-thread")

        # Set value
        await state.set("key1", "value1")

        # Get value
        value = await state.get("key1")
        assert value == "value1"

    async def test_get_default(self):
        """State get returns default for missing keys."""
        state = StateManager(thread_id="test-thread")

        value = await state.get("missing_key", "default")
        assert value == "default"

    async def test_get_missing_no_default(self):
        """State get returns None for missing keys without default."""
        state = StateManager(thread_id="test-thread")

        value = await state.get("missing_key")
        assert value is None

    async def test_update_multiple(self):
        """State can update multiple keys atomically."""
        state = StateManager(thread_id="test-thread")

        # Update multiple
        await state.update({
            "key1": "value1",
            "key2": "value2",
            "key3": "value3"
        })

        assert await state.get("key1") == "value1"
        assert await state.get("key2") == "value2"
        assert await state.get("key3") == "value3"

    async def test_delete(self):
        """State can delete keys."""
        state = StateManager(thread_id="test-thread")

        # Set and delete
        await state.set("key1", "value1")
        result = await state.delete("key1")

        assert result is True
        assert await state.get("key1") is None

    async def test_delete_missing(self):
        """Deleting missing key returns False."""
        state = StateManager(thread_id="test-thread")

        result = await state.delete("missing_key")
        assert result is False

    async def test_clear(self):
        """State can be cleared."""
        state = StateManager(thread_id="test-thread")

        # Set multiple keys
        await state.set("key1", "value1")
        await state.set("key2", "value2")

        # Clear
        await state.clear()

        assert await state.get("key1") is None
        assert await state.get("key2") is None

    async def test_snapshot(self):
        """State can create immutable snapshot."""
        state = StateManager(thread_id="test-thread")

        # Set state
        await state.set("key1", "value1")
        await state.set("key2", "value2")

        # Get snapshot
        snapshot = await state.snapshot()

        assert snapshot == {"key1": "value1", "key2": "value2"}

        # Modify snapshot doesn't affect state
        snapshot["key3"] = "value3"
        assert await state.get("key3") is None

    async def test_versioning(self):
        """State maintains version history."""
        state = StateManager(thread_id="test-thread")

        assert state.version_count() == 0

        # Each set creates a version
        await state.set("key1", "value1")
        assert state.version_count() == 1

        await state.set("key2", "value2")
        assert state.version_count() == 2

        await state.set("key1", "updated")
        assert state.version_count() == 3

    async def test_rollback_single_step(self):
        """State can rollback one step."""
        state = StateManager(thread_id="test-thread")

        # Set values
        await state.set("key1", "value1")
        await state.set("key2", "value2")

        # Rollback one step
        result = await state.rollback(steps=1)

        assert result is True
        assert await state.get("key1") == "value1"
        assert await state.get("key2") is None

    async def test_rollback_multiple_steps(self):
        """State can rollback multiple steps."""
        state = StateManager(thread_id="test-thread")

        # Set values
        await state.set("key1", "v1")
        await state.set("key2", "v2")
        await state.set("key3", "v3")

        # Rollback 2 steps
        result = await state.rollback(steps=2)

        assert result is True
        assert await state.get("key1") == "v1"
        assert await state.get("key2") is None
        assert await state.get("key3") is None

    async def test_rollback_insufficient_history(self):
        """Rollback with insufficient history returns False."""
        state = StateManager(thread_id="test-thread")

        # Only one version
        await state.set("key1", "value1")

        # Try to rollback 2 steps
        result = await state.rollback(steps=2)

        assert result is False

    async def test_get_history(self):
        """State can retrieve history."""
        state = StateManager(thread_id="test-thread")

        # Create history
        await state.set("key1", "v1")
        await state.set("key2", "v2")
        await state.set("key3", "v3")

        # Get history
        history = await state.get_history(limit=2)

        assert len(history) == 2
        # Most recent first
        assert history[0] == {"key1": "v1", "key2": "v2"}
        assert history[1] == {"key1": "v1"}

    async def test_persistence_with_checkpointer(self):
        """State persists to checkpointer."""
        checkpointer = MemoryCheckpointer()

        state = StateManager(thread_id="test-thread", checkpointer=checkpointer)

        # Set value (should persist)
        await state.set("key1", "value1")

        # Verify checkpoint exists
        checkpoints = await checkpointer.list_checkpoints(thread_id="test-thread")
        assert len(checkpoints) > 0

    async def test_restore_from_checkpoint(self):
        """State can restore from checkpointer."""
        checkpointer = MemoryCheckpointer()

        # Create and populate state
        state1 = StateManager(thread_id="test-thread", checkpointer=checkpointer)
        await state1.set("key1", "value1")
        await state1.set("key2", "value2")

        # Create new state instance and restore
        state2 = StateManager(thread_id="test-thread", checkpointer=checkpointer)
        result = await state2.restore_from_checkpoint()

        assert result is True
        assert await state2.get("key1") == "value1"
        assert await state2.get("key2") == "value2"

    async def test_thread_isolation(self):
        """Different threads have isolated state."""
        state1 = StateManager(thread_id="thread-1")
        state2 = StateManager(thread_id="thread-2")

        # Set in thread1
        await state1.set("key", "value1")

        # Set in thread2
        await state2.set("key", "value2")

        # Verify isolation
        assert await state1.get("key") == "value1"
        assert await state2.get("key") == "value2"

    async def test_state_repr(self):
        """State has useful repr."""
        state = StateManager(thread_id="test-thread")
        await state.set("key1", "value1")
        await state.set("key2", "value2")

        repr_str = repr(state)
        assert "test-thread" in repr_str
        assert "keys=2" in repr_str
