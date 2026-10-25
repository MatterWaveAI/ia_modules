"""
In-memory checkpoint storage for development and testing
"""

import asyncio
import uuid
import copy
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import defaultdict

from .core import (
    BaseCheckpointer,
    Checkpoint,
    CheckpointStatus
)


class MemoryCheckpointer(BaseCheckpointer):
    """
    In-memory checkpoint storage.

    Perfect for development, testing, and simple use cases.
    Data is lost when process exits.

    Example:
        >>> checkpointer = MemoryCheckpointer()
        >>> checkpoint_id = await checkpointer.save_checkpoint(
        ...     thread_id="test-123",
        ...     pipeline_id="my-pipeline",
        ...     step_id="step1",
        ...     step_index=0,
        ...     state={'data': 'value'}
        ... )
    """

    def __init__(self):
        """Initialize memory storage"""
        self.checkpoints: Dict[str, List[Checkpoint]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def save_checkpoint(
        self,
        thread_id: str,
        pipeline_id: str,
        step_id: str,
        step_index: int,
        state: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None,
        step_name: Optional[str] = None,
        parent_checkpoint_id: Optional[str] = None
    ) -> str:
        """Save checkpoint to memory"""
        checkpoint_id = f"ckpt-{uuid.uuid4()}"

        checkpoint = Checkpoint(
            checkpoint_id=checkpoint_id,
            thread_id=thread_id,
            pipeline_id=pipeline_id,
            step_id=step_id,
            step_index=step_index,
            step_name=step_name or step_id,
            timestamp=datetime.now(),
            state=copy.deepcopy(state),
            metadata=copy.deepcopy(metadata or {}),
            status=CheckpointStatus.COMPLETED,
            parent_checkpoint_id=parent_checkpoint_id
        )

        async with self._lock:
            self.checkpoints[thread_id].append(checkpoint)

        return checkpoint_id

    async def load_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: Optional[str] = None
    ) -> Optional[Checkpoint]:
        """Load checkpoint from memory"""
        async with self._lock:
            checkpoints = self.checkpoints.get(thread_id, [])

            if not checkpoints:
                return None

            if checkpoint_id:
                for cp in checkpoints:
                    if cp.checkpoint_id == checkpoint_id:
                        return Checkpoint(
                            checkpoint_id=cp.checkpoint_id,
                            thread_id=cp.thread_id,
                            pipeline_id=cp.pipeline_id,
                            pipeline_version=cp.pipeline_version,
                            step_id=cp.step_id,
                            step_index=cp.step_index,
                            step_name=cp.step_name,
                            timestamp=cp.timestamp,
                            state=copy.deepcopy(cp.state),
                            metadata=copy.deepcopy(cp.metadata),
                            status=cp.status,
                            parent_checkpoint_id=cp.parent_checkpoint_id
                        )
                return None
            else:
                latest = checkpoints[-1]
                return Checkpoint(
                    checkpoint_id=latest.checkpoint_id,
                    thread_id=latest.thread_id,
                    pipeline_id=latest.pipeline_id,
                    pipeline_version=latest.pipeline_version,
                    step_id=latest.step_id,
                    step_index=latest.step_index,
                    step_name=latest.step_name,
                    timestamp=latest.timestamp,
                    state=copy.deepcopy(latest.state),
                    metadata=copy.deepcopy(latest.metadata),
                    status=latest.status,
                    parent_checkpoint_id=latest.parent_checkpoint_id
                )

    async def list_checkpoints(
        self,
        thread_id: str,
        pipeline_id: Optional[str] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[Checkpoint]:
        """List checkpoints for thread"""
        async with self._lock:
            checkpoints = self.checkpoints.get(thread_id, [])
            sorted_checkpoints = sorted(checkpoints, key=lambda cp: cp.timestamp, reverse=True)
            paginated = sorted_checkpoints[offset:offset + limit]

            return [
                Checkpoint(
                    checkpoint_id=cp.checkpoint_id,
                    thread_id=cp.thread_id,
                    pipeline_id=cp.pipeline_id,
                    pipeline_version=cp.pipeline_version,
                    step_id=cp.step_id,
                    step_index=cp.step_index,
                    step_name=cp.step_name,
                    timestamp=cp.timestamp,
                    state=copy.deepcopy(cp.state),
                    metadata=copy.deepcopy(cp.metadata),
                    status=cp.status,
                    parent_checkpoint_id=cp.parent_checkpoint_id
                )
                for cp in paginated
            ]

    async def delete_checkpoints(
        self,
        thread_id: str,
        pipeline_id: Optional[str] = None,
        before: Optional[datetime] = None,
        keep_latest: int = 0,
    ) -> int:
        """Delete checkpoints"""
        async with self._lock:
            checkpoints = self.checkpoints.get(thread_id, [])

            if not checkpoints:
                return 0

            sorted_checkpoints = sorted(checkpoints, key=lambda cp: cp.timestamp, reverse=True)
            to_delete = []

            if keep_latest > 0:
                to_delete = sorted_checkpoints[keep_latest:]
            elif before:
                to_delete = [cp for cp in checkpoints if cp.timestamp < before]
            else:
                to_delete = list(checkpoints)

            for cp in to_delete:
                checkpoints.remove(cp)

            if checkpoints:
                self.checkpoints[thread_id] = checkpoints
            else:
                del self.checkpoints[thread_id]

            return len(to_delete)

    async def get_checkpoint_stats(
        self,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get checkpoint statistics"""
        async with self._lock:
            if thread_id:
                checkpoints = self.checkpoints.get(thread_id, [])

                if not checkpoints:
                    return {'total_checkpoints': 0, 'thread_id': thread_id}

                timestamps = [cp.timestamp for cp in checkpoints]
                return {
                    'total_checkpoints': len(checkpoints),
                    'oldest_checkpoint': min(timestamps),
                    'newest_checkpoint': max(timestamps),
                    'thread_id': thread_id
                }
            else:
                all_threads = list(self.checkpoints.keys())
                total_checkpoints = sum(len(cps) for cps in self.checkpoints.values())

                if total_checkpoints == 0:
                    return {'total_checkpoints': 0, 'threads': []}

                all_timestamps = []
                for cps in self.checkpoints.values():
                    all_timestamps.extend([cp.timestamp for cp in cps])

                return {
                    'total_checkpoints': total_checkpoints,
                    'oldest_checkpoint': min(all_timestamps) if all_timestamps else None,
                    'newest_checkpoint': max(all_timestamps) if all_timestamps else None,
                    'threads': all_threads
                }

    async def close(self) -> None:
        """Close (no-op for memory backend)"""
        pass

    def clear_all(self) -> None:
        """Clear all checkpoints (useful for testing)"""
        self.checkpoints.clear()
