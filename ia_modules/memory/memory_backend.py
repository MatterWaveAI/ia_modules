"""
In-memory conversation memory for development and testing
"""

import asyncio
import uuid
import copy
from typing import Dict, List, Optional, Any
from datetime import datetime
from collections import defaultdict

from .core import ConversationMemory, Message, MessageRole


class MemoryConversationMemory(ConversationMemory):
    """
    In-memory conversation memory storage.

    Perfect for development, testing, and simple use cases.
    Data is lost when process exits.

    Example:
        >>> memory = MemoryConversationMemory()
        >>> await memory.initialize()
        >>> await memory.add_message(
        ...     thread_id="conv-123",
        ...     role="user",
        ...     content="Hello!"
        ... )
    """

    def __init__(self):
        """Initialize memory storage"""
        self.messages: Dict[str, List[Message]] = defaultdict(list)  # thread_id -> messages
        self.user_messages: Dict[str, List[str]] = defaultdict(list)  # user_id -> message_ids
        self._lock = asyncio.Lock()

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
        """Add message to memory"""
        message_id = f"msg-{uuid.uuid4()}"

        message = Message(
            message_id=message_id,
            thread_id=thread_id,
            user_id=user_id,
            role=MessageRole(role),
            content=content,
            metadata=copy.deepcopy(metadata or {}),
            timestamp=datetime.now(),
            function_call=copy.deepcopy(function_call),
            function_name=function_name
        )

        async with self._lock:
            self.messages[thread_id].append(message)

            # Track user messages for long-term memory
            if user_id:
                self.user_messages[user_id].append(message_id)

        return message_id

    async def get_messages(
        self,
        thread_id: str,
        limit: int = 10,
        offset: int = 0
    ) -> List[Message]:
        """Get messages for thread"""
        async with self._lock:
            messages = self.messages.get(thread_id, [])

            # Sort by timestamp descending (most recent first)
            sorted_messages = sorted(messages, key=lambda m: m.timestamp, reverse=True)

            # Apply pagination
            paginated = sorted_messages[offset:offset + limit]

            # Return deep copies
            return [self._copy_message(msg) for msg in paginated]

    async def get_user_messages(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Message]:
        """Get all messages for user across all threads"""
        async with self._lock:
            message_ids = self.user_messages.get(user_id, [])

            if not message_ids:
                return []

            # Collect all messages for this user
            user_msgs = []
            for thread_id, thread_messages in self.messages.items():
                for msg in thread_messages:
                    if msg.user_id == user_id:
                        user_msgs.append(msg)

            # Sort by timestamp descending
            sorted_messages = sorted(user_msgs, key=lambda m: m.timestamp, reverse=True)

            # Apply pagination
            paginated = sorted_messages[offset:offset + limit]

            return [self._copy_message(msg) for msg in paginated]

    async def search_messages(
        self,
        query: str,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Message]:
        """Search messages by content"""
        query_lower = query.lower()

        async with self._lock:
            matches = []

            if thread_id:
                # Search in specific thread
                messages = self.messages.get(thread_id, [])
                for msg in messages:
                    if query_lower in msg.content.lower():
                        if user_id is None or msg.user_id == user_id:
                            matches.append(msg)
            else:
                # Search across all threads
                for thread_messages in self.messages.values():
                    for msg in thread_messages:
                        if query_lower in msg.content.lower():
                            if user_id is None or msg.user_id == user_id:
                                matches.append(msg)

            # Sort by timestamp descending
            sorted_matches = sorted(matches, key=lambda m: m.timestamp, reverse=True)

            # Apply limit
            limited = sorted_matches[:limit]

            return [self._copy_message(msg) for msg in limited]

    async def delete_thread(self, thread_id: str) -> int:
        """Delete all messages in thread"""
        async with self._lock:
            messages = self.messages.get(thread_id, [])
            count = len(messages)

            # Remove from user_messages index
            for msg in messages:
                if msg.user_id and msg.message_id in self.user_messages.get(msg.user_id, []):
                    self.user_messages[msg.user_id].remove(msg.message_id)

            # Delete thread
            if thread_id in self.messages:
                del self.messages[thread_id]

            return count

    async def get_thread_stats(self, thread_id: str) -> Dict[str, Any]:
        """Get thread statistics"""
        async with self._lock:
            messages = self.messages.get(thread_id, [])

            if not messages:
                return {
                    'message_count': 0,
                    'thread_id': thread_id
                }

            timestamps = [msg.timestamp for msg in messages]
            participants = list(set([msg.user_id for msg in messages if msg.user_id]))

            return {
                'message_count': len(messages),
                'first_message': min(timestamps),
                'last_message': max(timestamps),
                'participants': participants,
                'thread_id': thread_id
            }

    def _copy_message(self, msg: Message) -> Message:
        """Deep copy message to prevent mutations"""
        return Message(
            message_id=msg.message_id,
            thread_id=msg.thread_id,
            user_id=msg.user_id,
            role=msg.role,
            content=msg.content,
            metadata=copy.deepcopy(msg.metadata),
            timestamp=msg.timestamp,
            function_call=copy.deepcopy(msg.function_call),
            function_name=msg.function_name
        )

    def clear_all(self) -> None:
        """Clear all messages (useful for testing)"""
        self.messages.clear()
        self.user_messages.clear()
