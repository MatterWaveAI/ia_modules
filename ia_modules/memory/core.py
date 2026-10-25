"""
Core conversation memory data structures and interface
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime
from enum import Enum


class MessageRole(Enum):
    """Message role in conversation"""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"
    FUNCTION = "function"


@dataclass
class Message:
    """
    Represents a single message in a conversation.

    Used for storing conversation history for AI agents.
    """

    # Identity
    message_id: str
    thread_id: str  # Conversation thread
    user_id: Optional[str] = None  # Long-term user memory

    # Message content
    role: MessageRole = MessageRole.USER
    content: str = ""

    # Optional metadata
    metadata: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)

    # Optional: function call data
    function_call: Optional[Dict[str, Any]] = None
    function_name: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert message to dictionary"""
        return {
            'message_id': self.message_id,
            'thread_id': self.thread_id,
            'user_id': self.user_id,
            'role': self.role.value,
            'content': self.content,
            'metadata': self.metadata,
            'timestamp': self.timestamp.isoformat(),
            'function_call': self.function_call,
            'function_name': self.function_name
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'Message':
        """Create message from dictionary"""
        return cls(
            message_id=data['message_id'],
            thread_id=data['thread_id'],
            user_id=data.get('user_id'),
            role=MessageRole(data.get('role', 'user')),
            content=data.get('content', ''),
            metadata=data.get('metadata', {}),
            timestamp=datetime.fromisoformat(data['timestamp']) if data.get('timestamp') else datetime.now(),
            function_call=data.get('function_call'),
            function_name=data.get('function_name')
        )


class ConversationMemory(ABC):
    """
    Abstract base class for conversation memory storage.

    Provides short-term (thread-based) and long-term (user-based) memory.
    """

    @abstractmethod
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
        """
        Add a message to conversation history.

        Args:
            thread_id: Conversation thread ID
            role: Message role ('user', 'assistant', 'system', 'function')
            content: Message content
            user_id: User ID for long-term memory (optional)
            metadata: Additional metadata (optional)
            function_call: Function call data (optional)
            function_name: Function name (optional)

        Returns:
            message_id: Unique message identifier

        Example:
            >>> memory = ConversationMemory(...)
            >>> await memory.add_message(
            ...     thread_id="conv-123",
            ...     role="user",
            ...     content="Hello, how are you?",
            ...     user_id="user-456"
            ... )
        """
        pass

    @abstractmethod
    async def get_messages(
        self,
        thread_id: str,
        limit: int = 10,
        offset: int = 0
    ) -> List[Message]:
        """
        Get messages for a thread (most recent first).

        Args:
            thread_id: Conversation thread ID
            limit: Maximum number of messages
            offset: Pagination offset

        Returns:
            List of Message objects

        Example:
            >>> messages = await memory.get_messages("conv-123", limit=10)
            >>> for msg in messages:
            ...     print(f"{msg.role}: {msg.content}")
        """
        pass

    @abstractmethod
    async def get_user_messages(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Message]:
        """
        Get all messages for a user across all threads (long-term memory).

        Args:
            user_id: User ID
            limit: Maximum number of messages
            offset: Pagination offset

        Returns:
            List of Message objects

        Example:
            >>> # Get user's conversation history across all sessions
            >>> history = await memory.get_user_messages("user-456", limit=100)
        """
        pass

    @abstractmethod
    async def search_messages(
        self,
        query: str,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Message]:
        """
        Search messages by content.

        Args:
            query: Search query
            thread_id: Filter by thread (optional)
            user_id: Filter by user (optional)
            limit: Maximum results

        Returns:
            List of matching Message objects

        Example:
            >>> # Search user's past conversations
            >>> results = await memory.search_messages(
            ...     query="machine learning",
            ...     user_id="user-456"
            ... )
        """
        pass

    @abstractmethod
    async def delete_thread(self, thread_id: str) -> int:
        """
        Delete all messages in a thread.

        Args:
            thread_id: Thread to delete

        Returns:
            Number of messages deleted

        Example:
            >>> count = await memory.delete_thread("conv-123")
        """
        pass

    @abstractmethod
    async def get_thread_stats(self, thread_id: str) -> Dict[str, Any]:
        """
        Get statistics for a thread.

        Args:
            thread_id: Thread ID

        Returns:
            Dictionary with stats:
                - message_count: int
                - first_message: datetime
                - last_message: datetime
                - participants: List[str]

        Example:
            >>> stats = await memory.get_thread_stats("conv-123")
            >>> print(f"Messages: {stats['message_count']}")
        """
        pass

    async def close(self) -> None:
        """Close memory backend (cleanup)"""
        pass
