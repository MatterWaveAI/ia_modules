"""SQL-based checkpoint storage implementation"""

from typing import Dict, Any, Optional, List
from datetime import datetime
import json
import uuid

from .core import BaseCheckpointer, Checkpoint, CheckpointSaveError, CheckpointLoadError


def _as_json(value: Any) -> Any:
    """JSONB columns arrive parsed from PostgreSQL and as text from SQLite."""
    if value is None or isinstance(value, (dict, list)):
        return value
    return json.loads(value)


def _as_datetime(value: Any) -> Optional[datetime]:
    """TIMESTAMP columns arrive as datetime from PostgreSQL and as text from SQLite."""
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


class SQLCheckpointer(BaseCheckpointer):
    """
    SQL-based checkpoint storage using DatabaseManager.

    Works with PostgreSQL and SQLite using named parameters (:param).

    Example:
        >>> from nexusql import DatabaseManager
        >>> from ia_modules.database import MIGRATIONS_DIR
        >>> db = DatabaseManager("postgresql://localhost/mydb")
        >>> await db.initialize(app_migration_paths=[str(MIGRATIONS_DIR)])
        >>> checkpointer = SQLCheckpointer(db)
    """

    def __init__(self, db_manager):
        """
        Initialize with a connected database.

        Args:
            db_manager: nexusql DatabaseManager or an ia_modules database adapter;
                either way it offers table_exists() and execute_async().
        """
        self.db = db_manager

        # Schema comes from ia_modules' migrations (V001__complete_schema.sql)
        if not self.db.table_exists("pipeline_checkpoints"):
            raise CheckpointSaveError(
                "pipeline_checkpoints table not found. Run database migrations first."
            )

    # execute_async is the one query method a DatabaseManager and an adapter
    # share: a SELECT returns its rows as a list of dicts, a write returns an
    # empty list. Reads and writes both go through it.

    async def _rows(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        return await self.db.execute_async(query, params) or []

    async def _row(self, query: str, params: Optional[Dict[str, Any]] = None) -> Optional[Dict[str, Any]]:
        rows = await self._rows(query, params)
        return rows[0] if rows else None

    @staticmethod
    def _checkpoint(row: Dict[str, Any]) -> Checkpoint:
        parent = row["parent_checkpoint_id"]
        return Checkpoint(
            checkpoint_id=str(row["checkpoint_id"]),
            thread_id=row["thread_id"],
            pipeline_id=row["pipeline_id"],
            step_id=row["step_id"],
            step_index=row["step_index"],
            step_name=row["step_name"],
            state=_as_json(row["state"]),
            timestamp=_as_datetime(row["timestamp"]),
            metadata=_as_json(row["metadata"]) or {},
            parent_checkpoint_id=str(parent) if parent is not None else None,
        )

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
        """Save checkpoint to SQL database"""
        checkpoint_id = str(uuid.uuid4())

        query = """
        INSERT INTO pipeline_checkpoints (
            checkpoint_id, thread_id, pipeline_id, step_id, step_index,
            step_name, state, metadata, parent_checkpoint_id, timestamp
        ) VALUES (
            :checkpoint_id, :thread_id, :pipeline_id, :step_id, :step_index,
            :step_name, :state, :metadata, :parent_checkpoint_id, :timestamp
        )
        """

        params = {
            "checkpoint_id": checkpoint_id,
            "thread_id": thread_id,
            "pipeline_id": pipeline_id,
            "step_id": step_id,
            "step_index": step_index,
            "step_name": step_name,
            "state": json.dumps(state),
            "metadata": json.dumps(metadata or {}),
            "parent_checkpoint_id": parent_checkpoint_id,
            "timestamp": datetime.now().isoformat()
        }

        try:
            await self.db.execute_async(query, params)
            return checkpoint_id
        except Exception as e:
            raise CheckpointSaveError(f"Failed to save checkpoint: {e}")

    async def load_checkpoint(
        self,
        thread_id: str,
        checkpoint_id: Optional[str] = None
    ) -> Optional[Checkpoint]:
        """Load checkpoint from SQL database"""
        if checkpoint_id:
            query = """
            SELECT * FROM pipeline_checkpoints
            WHERE thread_id = :thread_id AND checkpoint_id = :checkpoint_id
            """
            params = {"thread_id": thread_id, "checkpoint_id": checkpoint_id}
        else:
            query = """
            SELECT * FROM pipeline_checkpoints
            WHERE thread_id = :thread_id
            ORDER BY timestamp DESC
            LIMIT 1
            """
            params = {"thread_id": thread_id}

        try:
            row = await self._row(query, params)
            if not row:
                return None
            return self._checkpoint(row)
        except Exception as e:
            raise CheckpointLoadError(f"Failed to load checkpoint: {e}")

    async def list_checkpoints(
        self,
        thread_id: str,
        pipeline_id: Optional[str] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[Checkpoint]:
        """List checkpoints from SQL database"""
        if pipeline_id:
            query = """
            SELECT * FROM pipeline_checkpoints
            WHERE thread_id = :thread_id AND pipeline_id = :pipeline_id
            ORDER BY timestamp DESC
            LIMIT :limit OFFSET :offset
            """
            params = {
                "thread_id": thread_id,
                "pipeline_id": pipeline_id,
                "limit": limit,
                "offset": offset
            }
        else:
            query = """
            SELECT * FROM pipeline_checkpoints
            WHERE thread_id = :thread_id
            ORDER BY timestamp DESC
            LIMIT :limit OFFSET :offset
            """
            params = {"thread_id": thread_id, "limit": limit, "offset": offset}

        try:
            rows = await self._rows(query, params)
            return [self._checkpoint(row) for row in rows]
        except Exception as e:
            raise CheckpointLoadError(f"Failed to list checkpoints: {e}")

    async def delete_checkpoint(self, thread_id: str, checkpoint_id: str) -> bool:
        """Delete specific checkpoint"""
        query = """
        DELETE FROM pipeline_checkpoints
        WHERE thread_id = :thread_id AND checkpoint_id = :checkpoint_id
        """
        params = {"thread_id": thread_id, "checkpoint_id": checkpoint_id}

        try:
            await self.db.execute_async(query, params)
            return True
        except Exception:
            return False

    async def delete_checkpoints(
        self,
        thread_id: str,
        pipeline_id: Optional[str] = None,
        before: Optional[datetime] = None,
        keep_latest: int = 0,
    ) -> int:
        """Delete a thread's checkpoints, optionally only one pipeline's.

        keep_latest > 0 keeps that many newest and deletes the rest; otherwise
        before deletes the ones older than it; with neither, all are deleted.
        Returns the number deleted.
        """
        where = "thread_id = :thread_id"
        params: Dict[str, Any] = {"thread_id": thread_id}
        if pipeline_id:
            where += " AND pipeline_id = :pipeline_id"
            params["pipeline_id"] = pipeline_id
        if before is not None and keep_latest <= 0:
            where += " AND timestamp < :before"
            params["before"] = before.isoformat() if isinstance(before, datetime) else before

        # execute_async returns no row count, so select the ids first; that is
        # also what lets keep_latest spare the newest rows.
        try:
            rows = await self._rows(
                f"SELECT checkpoint_id FROM pipeline_checkpoints WHERE {where} ORDER BY timestamp DESC",
                params,
            )
            doomed = [str(row["checkpoint_id"]) for row in rows][max(keep_latest, 0):]
            if not doomed:
                return 0
            ids = {f"id_{i}": checkpoint_id for i, checkpoint_id in enumerate(doomed)}
            placeholders = ", ".join(f":{key}" for key in ids)
            await self.db.execute_async(
                f"DELETE FROM pipeline_checkpoints WHERE checkpoint_id IN ({placeholders})", ids
            )
            return len(doomed)
        except Exception:
            return 0

    async def get_checkpoint_stats(
        self,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get checkpoint statistics"""
        if thread_id:
            query = """
            SELECT COUNT(*) as total, MIN(timestamp) as oldest, MAX(timestamp) as newest
            FROM pipeline_checkpoints
            WHERE thread_id = :thread_id
            """
            row = await self._row(query, {"thread_id": thread_id})

            return {
                'total_checkpoints': row['total'] if row else 0,
                'oldest_checkpoint': _as_datetime(row['oldest']) if row else None,
                'newest_checkpoint': _as_datetime(row['newest']) if row else None,
                'thread_id': thread_id
            }
        else:
            query = """
            SELECT COUNT(*) as total, MIN(timestamp) as oldest, MAX(timestamp) as newest,
                   COUNT(DISTINCT thread_id) as thread_count
            FROM pipeline_checkpoints
            """
            row = await self._row(query)

            threads_query = "SELECT DISTINCT thread_id FROM pipeline_checkpoints"
            threads = await self._rows(threads_query)

            return {
                'total_checkpoints': row['total'] if row else 0,
                'oldest_checkpoint': _as_datetime(row['oldest']) if row else None,
                'newest_checkpoint': _as_datetime(row['newest']) if row else None,
                'threads': [t['thread_id'] for t in threads]
            }

    async def close(self) -> None:
        """Close (no-op for SQL - DatabaseManager handles connections)"""
        pass
