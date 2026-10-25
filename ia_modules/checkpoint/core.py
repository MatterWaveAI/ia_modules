"""
Core checkpoint data structures and base interface
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum


class CheckpointStatus(Enum):
    """Checkpoint status"""
    PENDING = "pending"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class Checkpoint:
    """
    Represents a saved pipeline execution state.

    A checkpoint captures the complete state of a pipeline at a specific step,
    allowing execution to be paused and resumed later.
    """

    # Identity
    checkpoint_id: str
    thread_id: str  # Thread/conversation/user ID for isolation
    pipeline_id: str

    # Execution state
    step_id: str
    step_index: int

    # Optional fields (must come after required fields)
    pipeline_version: Optional[str] = None
    step_name: Optional[str] = None

    # State data
    state: Dict[str, Any] = field(default_factory=dict)
    # State should contain:
    # {
    #     'pipeline_input': {...},      # Original input
    #     'steps': {                     # Results from each step
    #         'step1': {...},
    #         'step2': {...}
    #     },
    #     'current_data': {...}         # Data passed to next step
    # }

    # Metadata
    timestamp: datetime = field(default_factory=datetime.now)
    metadata: Dict[str, Any] = field(default_factory=dict)
    status: CheckpointStatus = CheckpointStatus.COMPLETED

    # Optional: parent checkpoint for history tracking
    parent_checkpoint_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert checkpoint to dictionary"""
        return {
            'checkpoint_id': self.checkpoint_id,
            'thread_id': self.thread_id,
            'pipeline_id': self.pipeline_id,
            'pipeline_version': self.pipeline_version,
            'step_id': self.step_id,
            'step_index': self.step_index,
            'step_name': self.step_name,
            'state': self.state,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
            'status': self.status.value,
            'parent_checkpoint_id': self.parent_checkpoint_id
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Checkpoint':
        """Create checkpoint from dictionary"""
        return cls(
            checkpoint_id=data['checkpoint_id'],
            thread_id=data['thread_id'],
            pipeline_id=data['pipeline_id'],
            pipeline_version=data.get('pipeline_version'),
            step_id=data['step_id'],
            step_index=data['step_index'],
            step_name=data.get('step_name'),
            state=data.get('state', {}),
            timestamp=datetime.fromisoformat(data['timestamp']) if data.get('timestamp') else datetime.now(),
            metadata=data.get('metadata', {}),
            status=CheckpointStatus(data.get('status', 'completed')),
            parent_checkpoint_id=data.get('parent_checkpoint_id')
        )


class CheckpointError(Exception):
    """Base exception for checkpoint errors"""
    pass


class CheckpointSaveError(CheckpointError):
    """Error saving checkpoint"""
    pass


class CheckpointLoadError(CheckpointError):
    """Error loading checkpoint"""
    pass


class CheckpointDeleteError(CheckpointError):
    """Error deleting checkpoint"""
    pass


class BaseCheckpointer(ABC):
    """
    Abstract base class for checkpoint storage backends.

    Implementations must provide methods to save, load, list, and delete checkpoints.
    All initialization must happen in __init__ constructor.
    """

    @abstractmethod
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
        """
        Save a checkpoint.

        Args:
            thread_id: Thread/conversation identifier (for isolation)
            pipeline_id: Pipeline identifier
            step_id: Current step identifier
            step_index: Step index in execution order
            state: Complete pipeline state (context)
            metadata: Additional metadata (optional)
            step_name: Human-readable step name (optional)
            parent_checkpoint_id: Parent checkpoint ID for history (optional)

        Returns:
            checkpoint_id: Unique identifier for this checkpoint

        Raises:
            CheckpointSaveError: If save fails

        Example:
            >>> checkpoint_id = await checkpointer.save_checkpoint(
            ...     thread_id="user-123",
            ...     pipeline_id="data-pipeline",
            ...     step_id="transform_data",
            ...     step_index=2,
            ...     state={'pipeline_input': {...}, 'steps': {...}},
            ...     metadata={'user': 'john@example.com'}
            ... )
        """
        pass

    @abstractmethod
    async def load_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: Optional[str] = None
    ) -> Optional[Checkpoint]:
        """
        Load a checkpoint.

        If checkpoint_id is None, loads the latest checkpoint for the thread.

        Args:
            thread_id: Thread identifier
            checkpoint_id: Specific checkpoint ID (optional, defaults to latest)

        Returns:
            Checkpoint object or None if not found

        Raises:
            CheckpointLoadError: If load fails

        Example:
            >>> # Load latest checkpoint
            >>> checkpoint = await checkpointer.load_checkpoint("user-123")
            >>>
            >>> # Load specific checkpoint
            >>> checkpoint = await checkpointer.load_checkpoint(
            ...     "user-123",
            ...     checkpoint_id="ckpt-abc123"
            ... )
        """
        pass

    @abstractmethod
    async def list_checkpoints(
        self,
        thread_id: str,
        pipeline_id: Optional[str] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[Checkpoint]:
        """
        List checkpoints for a thread (most recent first).

        Args:
            thread_id: Thread identifier
            limit: Maximum number of checkpoints to return
            offset: Offset for pagination

        Returns:
            List of Checkpoint objects

        Example:
            >>> checkpoints = await checkpointer.list_checkpoints(
            ...     "user-123",
            ...     limit=5
            ... )
            >>> for cp in checkpoints:
            ...     print(f"{cp.step_id} at {cp.timestamp}")
        """
        pass

    @abstractmethod
    async def delete_checkpoints(
        self,
        thread_id: str,
        pipeline_id: Optional[str] = None,
        before: Optional[datetime] = None,
        keep_latest: int = 0,
    ) -> int:
        """
        Delete checkpoints for a thread.

        Args:
            thread_id: Thread identifier
            before: Delete checkpoints before this timestamp (optional)
            keep_latest: Keep N most recent checkpoints (default: 0 = delete all)

        Returns:
            Number of checkpoints deleted

        Raises:
            CheckpointDeleteError: If delete fails

        Example:
            >>> from datetime import datetime, timedelta
            >>>
            >>> # Delete all checkpoints older than 7 days
            >>> count = await checkpointer.delete_checkpoints(
            ...     "user-123",
            ...     before=datetime.now() - timedelta(days=7)
            ... )
            >>>
            >>> # Delete all but keep latest 5
            >>> count = await checkpointer.delete_checkpoints(
            ...     "user-123",
            ...     keep_latest=5
            ... )
        """
        pass

    @abstractmethod
    async def get_checkpoint_stats(
        self,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Get checkpoint statistics.

        Args:
            thread_id: Thread identifier (optional, returns stats for all threads if None)

        Returns:
            Dictionary with stats:
                - total_checkpoints: int
                - oldest_checkpoint: datetime
                - newest_checkpoint: datetime
                - total_size_bytes: int (if available)
                - threads: List[str] (if thread_id is None)

        Example:
            >>> stats = await checkpointer.get_checkpoint_stats("user-123")
            >>> print(f"Total: {stats['total_checkpoints']}")
        """
        pass

    async def close(self) -> None:
        """
        Close the checkpointer (cleanup connections, etc.)

        Optional method - override if your backend needs cleanup.

        Example:
            >>> await checkpointer.close()
        """
        pass
