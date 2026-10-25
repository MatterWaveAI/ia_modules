"""
SQL-based conversation memory using DatabaseInterface
"""

import inspect
import uuid
import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from .core import ConversationMemory, Message, MessageRole


def _as_datetime(value: Any) -> Optional[datetime]:
    """TIMESTAMP columns arrive as datetime from PostgreSQL and as text from SQLite."""
    if value is None or isinstance(value, datetime):
        return value
    return datetime.fromisoformat(value)


class SQLConversationMemory(ConversationMemory):
    """
    SQL-based conversation memory.

    Uses DatabaseInterface for PostgreSQL, SQLite, MySQL, DuckDB support.
    """

    def __init__(self, db_manager):
        self.db = db_manager
    async def add_message(
        self,
        thread_id: str,
        role: str,
        content: str,
        user_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        function_call: Optional[Dict[str, Any]] = None,
        function_name: Optional[str] = None
    ) -> str:
        """Add message to database"""
        message_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()

        metadata_json = json.dumps(metadata or {})
        function_call_json = json.dumps(function_call) if function_call else None

        query = """
            INSERT INTO conversation_messages
            (message_id, thread_id, user_id, role, content, metadata, timestamp, function_call, function_name)
            VALUES (:message_id, :thread_id, :user_id, :role, :content, :metadata, :timestamp, :function_call, :function_name)
        """
        params = {
            'message_id': message_id,
            'thread_id': thread_id,
            'user_id': user_id,
            'role': role,
            'content': content,
            'metadata': metadata_json,
            'timestamp': timestamp,
            'function_call': function_call_json,
            'function_name': function_name
        }

        await self.db.execute_async(query, params)
        return message_id

    async def get_messages(
        self,
        thread_id: str,
        limit: int = 10,
        offset: int = 0
    ) -> List[Message]:
        """Get messages for thread"""
        query = """
            SELECT * FROM conversation_messages
            WHERE thread_id = :thread_id
            ORDER BY timestamp DESC
            LIMIT :limit OFFSET :offset
        """
        params = {
            'thread_id': thread_id,
            'limit': limit,
            'offset': offset
        }

        rows = await self.db.execute_async(query, params)
        return [self._row_to_message(row) for row in rows]

    async def get_user_messages(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Message]:
        """Get all messages for user"""
        query = """
            SELECT * FROM conversation_messages
            WHERE user_id = :user_id
            ORDER BY timestamp DESC
            LIMIT :limit OFFSET :offset
        """
        params = {
            'user_id': user_id,
            'limit': limit,
            'offset': offset
        }

        rows = await self.db.execute_async(query, params)
        return [self._row_to_message(row) for row in rows]

    async def search_messages(
        self,
        query: str,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Message]:
        """Search messages by content"""
        conditions: List[str] = []
        params: Dict[str, Any] = {}

        # Build WHERE clause with named parameters
        conditions.append("content LIKE :search_query")
        params['search_query'] = f"%{query}%"

        if thread_id:
            conditions.append("thread_id = :thread_id")
            params['thread_id'] = thread_id

        if user_id:
            conditions.append("user_id = :user_id")
            params['user_id'] = user_id

        where_clause = " AND ".join(conditions)
        params['limit'] = limit

        sql_query = f"""
            SELECT * FROM conversation_messages
            WHERE {where_clause}
            ORDER BY timestamp DESC
            LIMIT :limit
        """

        rows = await self.db.execute_async(sql_query, params)
        return [self._row_to_message(row) for row in rows]

    async def delete_thread(self, thread_id: str) -> int:
        """Delete all messages in thread"""
        query = "DELETE FROM conversation_messages WHERE thread_id = :thread_id"
        params = {'thread_id': thread_id}

        # execute_async returns no row count, so count before deleting
        count = await self.db.execute_async(
            "SELECT COUNT(*) AS total FROM conversation_messages WHERE thread_id = :thread_id",
            params,
        )
        await self.db.execute_async(query, params)
        return int(count[0]['total']) if count else 0

    async def get_thread_stats(self, thread_id: str) -> Dict[str, Any]:
        """Get thread statistics"""
        query = """
            SELECT
                COUNT(*) as count,
                MIN(timestamp) as first_msg,
                MAX(timestamp) as last_msg,
                COUNT(DISTINCT user_id) as participant_count
            FROM conversation_messages
            WHERE thread_id = :thread_id
        """
        params = {'thread_id': thread_id}

        rows = await self.db.execute_async(query, params)
        row = rows[0]

        return {
            'message_count': row['count'],
            'first_message': _as_datetime(row['first_msg']),
            'last_message': _as_datetime(row['last_msg']),
            'thread_id': thread_id
        }

    async def close(self) -> None:
        """Close database connection"""
        # disconnect() is synchronous on a DatabaseManager and on the adapter
        result = self.db.disconnect()
        if inspect.isawaitable(result):
            await result

    def _row_to_message(self, row: Dict[str, Any]) -> Message:
        """Convert database row to Message"""
        metadata = json.loads(row['metadata']) if isinstance(row['metadata'], str) else row['metadata']
        function_call = json.loads(row['function_call']) if row['function_call'] and isinstance(row['function_call'], str) else row['function_call']

        return Message(
            message_id=row['message_id'],
            thread_id=row['thread_id'],
            user_id=row['user_id'],
            role=MessageRole(row['role']),
            content=row['content'],
            metadata=metadata,
            timestamp=datetime.fromisoformat(row['timestamp']) if isinstance(row['timestamp'], str) else row['timestamp'],
            function_call=function_call,
            function_name=row.get('function_name')
        )
