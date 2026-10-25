"""
Centralized state management for agent orchestration.

Provides thread-scoped state with versioning, rollback, and persistence.
"""

import asyncio
import copy
from typing import Dict, Any, Optional, List
from datetime import datetime
import logging


class StateManager:
    """
    Thread-scoped centralized state for multi-agent workflows.

    Features:
    - Thread isolation for multi-user support
    - State versioning for rollback
    - Persistence via checkpointer integration
    - Atomic updates with locking
    - Full state history

    Example:
        >>> state = StateManager(thread_id="user-123")
        >>>
        >>> # Write state
        >>> await state.set("plan", ["step1", "step2"])
        >>>
        >>> # Read state
        >>> plan = await state.get("plan")
        >>>
        >>> # Rollback
        >>> await state.rollback(steps=1)
    """

    def __init__(self, thread_id: str, checkpointer: Optional[Any] = None):
        """
        Initialize state manager.

        Args:
            thread_id: Thread identifier for isolation
            checkpointer: Optional checkpointer for persistence
        """
        self.thread_id = thread_id
        self.checkpointer = checkpointer
        self._state: Dict[str, Any] = {}
        self._versions: List[Dict[str, Any]] = []  # State history
        self._lock = asyncio.Lock()
        self.logger = logging.getLogger(f"StateManager.{thread_id}")

    async def get(self, key: str, default: Any = None) -> Any:
        """
        Get value from state.

        Args:
            key: State key
            default: Default value if key doesn't exist

        Returns:
            Value from state or default
        """
        async with self._lock:
            value = self._state.get(key, default)
            self.logger.debug(f"GET {key} = {value}")
            return value

    async def set(self, key: str, value: Any) -> None:
        """
        Set value in state with versioning.

        Creates a snapshot of state before update for rollback capability.

        Args:
            key: State key
            value: Value to store
        """
        async with self._lock:
            # Save current state to history
            self._versions.append(copy.deepcopy(self._state))

            # Update state
            self._state[key] = value
            self.logger.debug(f"SET {key} = {value}")

            # Persist if checkpointer available
            if self.checkpointer:
                await self._persist()

    async def update(self, updates: Dict[str, Any]) -> None:
        """
        Update multiple keys atomically.

        Args:
            updates: Dictionary of key-value pairs to update
        """
        async with self._lock:
            # Save current state to history
            self._versions.append(copy.deepcopy(self._state))

            # Apply all updates
            self._state.update(updates)
            self.logger.debug(f"UPDATE {len(updates)} keys")

            # Persist if checkpointer available
            if self.checkpointer:
                await self._persist()

    async def delete(self, key: str) -> bool:
        """
        Delete key from state.

        Args:
            key: State key to delete

        Returns:
            True if key existed, False otherwise
        """
        async with self._lock:
            if key in self._state:
                # Save current state to history
                self._versions.append(copy.deepcopy(self._state))

                del self._state[key]
                self.logger.debug(f"DELETE {key}")

                # Persist if checkpointer available
                if self.checkpointer:
                    await self._persist()

                return True

            return False

    async def clear(self) -> None:
        """Clear all state."""
        async with self._lock:
            # Save current state to history
            if self._state:
                self._versions.append(copy.deepcopy(self._state))

            self._state.clear()
            self.logger.debug("CLEAR all state")

            # Persist if checkpointer available
            if self.checkpointer:
                await self._persist()

    async def snapshot(self) -> Dict[str, Any]:
        """
        Get immutable snapshot of current state.

        Returns:
            Deep copy of current state
        """
        async with self._lock:
            return copy.deepcopy(self._state)

    async def rollback(self, steps: int = 1) -> bool:
        """
        Rollback state to previous version.

        Args:
            steps: Number of versions to roll back

        Returns:
            True if rollback successful, False if not enough history
        """
        async with self._lock:
            if len(self._versions) < steps:
                self.logger.warning(f"Cannot rollback {steps} steps, only {len(self._versions)} versions available")
                return False

            # Restore state from history
            self._state = self._versions[-(steps)]
            self._versions = self._versions[:-(steps)]

            self.logger.info(f"Rolled back {steps} step(s)")

            # Persist if checkpointer available
            if self.checkpointer:
                await self._persist()

            return True

    async def get_history(self, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get state history.

        Args:
            limit: Maximum number of historical states to return

        Returns:
            List of historical state snapshots (most recent first)
        """
        async with self._lock:
            history = list(reversed(self._versions[-limit:]))
            return [copy.deepcopy(state) for state in history]

    def version_count(self) -> int:
        """
        Get number of versions in history.

        Returns:
            Number of saved state versions
        """
        return len(self._versions)

    async def _persist(self) -> None:
        """Save state to checkpointer."""
        if not self.checkpointer:
            return

        try:
            await self.checkpointer.save_checkpoint(
                thread_id=self.thread_id,
                pipeline_id="agent_orchestration",
                step_id="state_snapshot",
                step_index=len(self._versions),
                state=self._state,
                metadata={
                    "timestamp": datetime.now().isoformat(),
                    "version": len(self._versions)
                }
            )
            self.logger.debug("State persisted to checkpointer")

        except Exception as e:
            self.logger.error(f"Failed to persist state: {e}")

    async def restore_from_checkpoint(self, checkpoint_id: Optional[str] = None) -> bool:
        """
        Restore state from checkpointer.

        Args:
            checkpoint_id: Specific checkpoint to restore, or None for latest

        Returns:
            True if restore successful, False otherwise
        """
        if not self.checkpointer:
            self.logger.warning("No checkpointer available for restore")
            return False

        try:
            # Load checkpoint
            checkpoint = await self.checkpointer.load_checkpoint(
                thread_id=self.thread_id,
                checkpoint_id=checkpoint_id
            )

            if not checkpoint:
                self.logger.warning(f"No checkpoint found for thread {self.thread_id}")
                return False

            async with self._lock:
                # Restore state
                self._state = copy.deepcopy(checkpoint.state)
                self.logger.info(f"State restored from checkpoint {checkpoint.checkpoint_id}")

            return True

        except Exception as e:
            self.logger.error(f"Failed to restore state: {e}")
            return False

    def __repr__(self) -> str:
        return f"<StateManager(thread_id={self.thread_id}, keys={len(self._state)}, versions={len(self._versions)})>"
