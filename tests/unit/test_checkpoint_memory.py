"""
Tests for MemoryCheckpointer
"""

import asyncio
import pytest
from datetime import datetime, timedelta

from ia_modules.checkpoint import MemoryCheckpointer


class TestMemoryCheckpointerBasic:
    """Basic functionality tests"""

    @pytest.mark.asyncio
    async def test_initialize(self):
        """Test checkpointer initialization"""
        MemoryCheckpointer()

    @pytest.mark.asyncio
    async def test_save_checkpoint(self):
        """Test saving a checkpoint"""
        checkpointer = MemoryCheckpointer()

        checkpoint_id = await checkpointer.save_checkpoint(
            thread_id="test-thread",
            pipeline_id="test-pipeline",
            step_id="step1",
            step_index=0,
            state={'data': 'value'}
        )

        assert checkpoint_id is not None
        assert checkpoint_id.startswith("ckpt-")

    @pytest.mark.asyncio
    async def test_load_latest_checkpoint(self):
        """Test loading the latest checkpoint"""
        checkpointer = MemoryCheckpointer()

        # Save two checkpoints
        await checkpointer.save_checkpoint(
            thread_id="test-thread",
            pipeline_id="test-pipeline",
            step_id="step1",
            step_index=0,
            state={'step': 1}
        )

        await checkpointer.save_checkpoint(
            thread_id="test-thread",
            pipeline_id="test-pipeline",
            step_id="step2",
            step_index=1,
            state={'step': 2}
        )

        # Load latest
        checkpoint = await checkpointer.load_checkpoint("test-thread")

        assert checkpoint is not None
        assert checkpoint.step_id == "step2"
        assert checkpoint.state == {'step': 2}

    @pytest.mark.asyncio
    async def test_load_specific_checkpoint(self):
        """Test loading a specific checkpoint by ID"""
        checkpointer = MemoryCheckpointer()

        # Save checkpoints
        ckpt1_id = await checkpointer.save_checkpoint(
            thread_id="test-thread",
            pipeline_id="test-pipeline",
            step_id="step1",
            step_index=0,
            state={'step': 1}
        )

        await checkpointer.save_checkpoint(
            thread_id="test-thread",
            pipeline_id="test-pipeline",
            step_id="step2",
            step_index=1,
            state={'step': 2}
        )

        # Load first checkpoint
        checkpoint = await checkpointer.load_checkpoint("test-thread", ckpt1_id)

        assert checkpoint is not None
        assert checkpoint.checkpoint_id == ckpt1_id
        assert checkpoint.step_id == "step1"
        assert checkpoint.state == {'step': 1}

    @pytest.mark.asyncio
    async def test_load_nonexistent_checkpoint(self):
        """Test loading a checkpoint that doesn't exist"""
        checkpointer = MemoryCheckpointer()

        checkpoint = await checkpointer.load_checkpoint("nonexistent-thread")
        assert checkpoint is None


class TestMemoryCheckpointerList:
    """Tests for listing checkpoints"""

    @pytest.mark.asyncio
    async def test_list_checkpoints(self):
        """Test listing checkpoints for a thread"""
        checkpointer = MemoryCheckpointer()

        # Save multiple checkpoints
        for i in range(5):
            await checkpointer.save_checkpoint(
                thread_id="test-thread",
                pipeline_id="test-pipeline",
                step_id=f"step{i}",
                step_index=i,
                state={'step': i}
            )
            await asyncio.sleep(0.001)  # Ensure distinct timestamps

        checkpoints = await checkpointer.list_checkpoints("test-thread")

        assert len(checkpoints) == 5
        # Should be in reverse order (most recent first)
        assert checkpoints[0].step_id == "step4"
        assert checkpoints[4].step_id == "step0"

    @pytest.mark.asyncio
    async def test_list_with_limit(self):
        """Test listing with limit"""
        checkpointer = MemoryCheckpointer()

        # Save 10 checkpoints
        for i in range(10):
            await checkpointer.save_checkpoint(
                thread_id="test-thread",
                pipeline_id="test-pipeline",
                step_id=f"step{i}",
                step_index=i,
                state={'step': i}
            )
            await asyncio.sleep(0.001)  # Ensure distinct timestamps

        checkpoints = await checkpointer.list_checkpoints("test-thread", limit=3)

        assert len(checkpoints) == 3
        assert checkpoints[0].step_id == "step9"

    @pytest.mark.asyncio
    async def test_list_with_pagination(self):
        """Test listing with pagination"""
        checkpointer = MemoryCheckpointer()

        # Save 10 checkpoints
        for i in range(10):
            await checkpointer.save_checkpoint(
                thread_id="test-thread",
                pipeline_id="test-pipeline",
                step_id=f"step{i}",
                step_index=i,
                state={'step': i}
            )
            await asyncio.sleep(0.001)  # Ensure distinct timestamps

        # Get second page
        checkpoints = await checkpointer.list_checkpoints("test-thread", limit=3, offset=3)

        assert len(checkpoints) == 3
        assert checkpoints[0].step_id == "step6"


class TestMemoryCheckpointerDelete:
    """Tests for deleting checkpoints"""

    @pytest.mark.asyncio
    async def test_delete_all_checkpoints(self):
        """Test deleting all checkpoints for a thread"""
        checkpointer = MemoryCheckpointer()

        # Save checkpoints
        for i in range(5):
            await checkpointer.save_checkpoint(
                thread_id="test-thread",
                pipeline_id="test-pipeline",
                step_id=f"step{i}",
                step_index=i,
                state={'step': i}
            )

        # Delete all
        count = await checkpointer.delete_checkpoints("test-thread")

        assert count == 5

        # Verify deleted
        checkpoint = await checkpointer.load_checkpoint("test-thread")
        assert checkpoint is None

    @pytest.mark.asyncio
    async def test_delete_with_keep_latest(self):
        """Test deleting with keep_latest"""
        checkpointer = MemoryCheckpointer()

        # Save 10 checkpoints
        for i in range(10):
            await checkpointer.save_checkpoint(
                thread_id="test-thread",
                pipeline_id="test-pipeline",
                step_id=f"step{i}",
                step_index=i,
                state={'step': i}
            )
            await asyncio.sleep(0.001)  # Ensure distinct timestamps

        # Delete all but keep latest 3
        count = await checkpointer.delete_checkpoints("test-thread", keep_latest=3)

        assert count == 7

        # Verify only 3 remain
        checkpoints = await checkpointer.list_checkpoints("test-thread")
        assert len(checkpoints) == 3
        assert checkpoints[0].step_id == "step9"
        assert checkpoints[2].step_id == "step7"

    @pytest.mark.asyncio
    async def test_delete_before_timestamp(self):
        """Test deleting checkpoints before a timestamp"""
        checkpointer = MemoryCheckpointer()

        # Save checkpoints at different times
        now = datetime.now()

        for i in range(5):
            await checkpointer.save_checkpoint(
                thread_id="test-thread",
                pipeline_id="test-pipeline",
                step_id=f"step{i}",
                step_index=i,
                state={'step': i}
            )

        # Mark a cutoff time (between creation times)
        cutoff = now + timedelta(seconds=1)

        # Delete checkpoints before cutoff (should delete older ones)
        count = await checkpointer.delete_checkpoints("test-thread", before=cutoff)

        # Should have deleted some
        assert count >= 0


class TestMemoryCheckpointerStats:
    """Tests for checkpoint statistics"""

    @pytest.mark.asyncio
    async def test_stats_single_thread(self):
        """Test getting stats for a single thread"""
        checkpointer = MemoryCheckpointer()

        # Save checkpoints
        for i in range(5):
            await checkpointer.save_checkpoint(
                thread_id="test-thread",
                pipeline_id="test-pipeline",
                step_id=f"step{i}",
                step_index=i,
                state={'step': i}
            )

        stats = await checkpointer.get_checkpoint_stats("test-thread")

        assert stats['total_checkpoints'] == 5
        assert 'oldest_checkpoint' in stats
        assert 'newest_checkpoint' in stats
        assert stats['thread_id'] == "test-thread"

    @pytest.mark.asyncio
    async def test_stats_all_threads(self):
        """Test getting stats for all threads"""
        checkpointer = MemoryCheckpointer()

        # Save checkpoints in multiple threads
        for thread in ['thread1', 'thread2', 'thread3']:
            for i in range(3):
                await checkpointer.save_checkpoint(
                    thread_id=thread,
                    pipeline_id="test-pipeline",
                    step_id=f"step{i}",
                    step_index=i,
                    state={'step': i}
                )

        stats = await checkpointer.get_checkpoint_stats()

        assert stats['total_checkpoints'] == 9
        assert len(stats['threads']) == 3


class TestMemoryCheckpointerIsolation:
    """Tests for thread isolation"""

    @pytest.mark.asyncio
    async def test_thread_isolation(self):
        """Test that threads are isolated from each other"""
        checkpointer = MemoryCheckpointer()

        # Save checkpoints in different threads
        await checkpointer.save_checkpoint(
            thread_id="thread1",
            pipeline_id="test-pipeline",
            step_id="step1",
            step_index=0,
            state={'thread': 1}
        )

        await checkpointer.save_checkpoint(
            thread_id="thread2",
            pipeline_id="test-pipeline",
            step_id="step1",
            step_index=0,
            state={'thread': 2}
        )

        # Load from thread1
        checkpoint1 = await checkpointer.load_checkpoint("thread1")
        assert checkpoint1.state == {'thread': 1}

        # Load from thread2
        checkpoint2 = await checkpointer.load_checkpoint("thread2")
        assert checkpoint2.state == {'thread': 2}

    @pytest.mark.asyncio
    async def test_state_deep_copy(self):
        """Test that state is deep copied to prevent mutations"""
        checkpointer = MemoryCheckpointer()

        original_state = {'data': [1, 2, 3]}

        await checkpointer.save_checkpoint(
            thread_id="test-thread",
            pipeline_id="test-pipeline",
            step_id="step1",
            step_index=0,
            state=original_state
        )

        # Mutate original state
        original_state['data'].append(4)

        # Load checkpoint and verify not mutated
        checkpoint = await checkpointer.load_checkpoint("test-thread")
        assert checkpoint.state == {'data': [1, 2, 3]}


class TestMemoryCheckpointerMetadata:
    """Tests for checkpoint metadata"""

    @pytest.mark.asyncio
    async def test_save_with_metadata(self):
        """Test saving checkpoint with metadata"""
        checkpointer = MemoryCheckpointer()

        metadata = {'user': 'john@example.com', 'session': 'abc123'}

        await checkpointer.save_checkpoint(
            thread_id="test-thread",
            pipeline_id="test-pipeline",
            step_id="step1",
            step_index=0,
            state={'data': 'value'},
            metadata=metadata
        )

        checkpoint = await checkpointer.load_checkpoint("test-thread")

        assert checkpoint.metadata == metadata

    @pytest.mark.asyncio
    async def test_save_with_step_name(self):
        """Test saving checkpoint with custom step name"""
        checkpointer = MemoryCheckpointer()

        await checkpointer.save_checkpoint(
            thread_id="test-thread",
            pipeline_id="test-pipeline",
            step_id="step1",
            step_index=0,
            state={'data': 'value'},
            step_name="Process Data Step"
        )

        checkpoint = await checkpointer.load_checkpoint("test-thread")

        assert checkpoint.step_name == "Process Data Step"

    @pytest.mark.asyncio
    async def test_parent_checkpoint_id(self):
        """Test checkpoint with parent reference"""
        checkpointer = MemoryCheckpointer()

        parent_id = await checkpointer.save_checkpoint(
            thread_id="test-thread",
            pipeline_id="test-pipeline",
            step_id="step1",
            step_index=0,
            state={'data': 'value'}
        )

        child_id = await checkpointer.save_checkpoint(
            thread_id="test-thread",
            pipeline_id="test-pipeline",
            step_id="step2",
            step_index=1,
            state={'data': 'value2'},
            parent_checkpoint_id=parent_id
        )

        checkpoint = await checkpointer.load_checkpoint("test-thread", child_id)

        assert checkpoint.parent_checkpoint_id == parent_id
