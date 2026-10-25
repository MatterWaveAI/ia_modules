"""
Unit tests for Memory system core functionality.

Tests the Message dataclass, MessageRole enum, and ConversationMemory interfaces.
"""
import asyncio
import pytest
from datetime import datetime
from ia_modules.memory.core import Message, MessageRole
from ia_modules.memory.memory_backend import MemoryConversationMemory


class TestMessageDataclass:
    """Test Message dataclass functionality."""

    def test_message_creation_minimal(self):
        """Message can be created with minimal required fields."""
        msg = Message(
            message_id="msg-1",
            thread_id="thread-1",
            content="Hello"
        )

        assert msg.message_id == "msg-1"
        assert msg.thread_id == "thread-1"
        assert msg.content == "Hello"
        assert msg.role == MessageRole.USER  # Default
        assert msg.user_id is None
        assert msg.metadata == {}
        assert isinstance(msg.timestamp, datetime)

    def test_message_creation_full(self):
        """Message can be created with all fields."""
        timestamp = datetime.now()
        metadata = {"source": "api", "ip": "192.168.1.1"}
        function_call = {"name": "get_weather", "arguments": "{}"}

        msg = Message(
            message_id="msg-1",
            thread_id="thread-1",
            user_id="user-123",
            role=MessageRole.ASSISTANT,
            content="The weather is sunny.",
            metadata=metadata,
            timestamp=timestamp,
            function_call=function_call,
            function_name="get_weather"
        )

        assert msg.message_id == "msg-1"
        assert msg.thread_id == "thread-1"
        assert msg.user_id == "user-123"
        assert msg.role == MessageRole.ASSISTANT
        assert msg.content == "The weather is sunny."
        assert msg.metadata == metadata
        assert msg.timestamp == timestamp
        assert msg.function_call == function_call
        assert msg.function_name == "get_weather"

    def test_message_roles(self):
        """All MessageRole enum values work correctly."""
        roles = [
            MessageRole.SYSTEM,
            MessageRole.USER,
            MessageRole.ASSISTANT,
            MessageRole.FUNCTION
        ]

        for role in roles:
            msg = Message(
                message_id=f"msg-{role.value}",
                thread_id="thread-1",
                role=role,
                content=f"Content for {role.value}"
            )
            assert msg.role == role


@pytest.mark.asyncio
class TestMemoryConversationMemory:
    """Test MemoryConversationMemory implementation."""

    async def test_initialize(self):
        """Memory backend can be initialized."""
        memory = MemoryConversationMemory()

        # Should not raise errors
        assert memory is not None

    async def test_add_message(self):
        """Messages can be added to memory."""
        memory = MemoryConversationMemory()

        message_id = await memory.add_message(
            thread_id="thread-1",
            role="user",
            content="Hello, world!"
        )

        assert message_id is not None
        assert len(message_id) > 0

    async def test_add_message_with_user_id(self):
        """Messages can be added with user_id for long-term memory."""
        memory = MemoryConversationMemory()

        message_id = await memory.add_message(
            thread_id="thread-1",
            user_id="user-123",
            role="user",
            content="Hello!"
        )

        assert message_id is not None

    async def test_add_message_with_metadata(self):
        """Messages can be added with custom metadata."""
        memory = MemoryConversationMemory()

        metadata = {"source": "web", "ip": "192.168.1.1"}

        await memory.add_message(
            thread_id="thread-1",
            role="user",
            content="Hello!",
            metadata=metadata
        )

        messages = await memory.get_messages("thread-1")
        assert len(messages) == 1
        assert messages[0].metadata == metadata

    async def test_add_message_with_function_call(self):
        """Messages can be added with function call data."""
        memory = MemoryConversationMemory()

        function_call = {"name": "get_weather", "arguments": '{"city": "SF"}'}

        await memory.add_message(
            thread_id="thread-1",
            role="assistant",
            content="Calling weather API...",
            function_call=function_call,
            function_name="get_weather"
        )

        messages = await memory.get_messages("thread-1")
        assert len(messages) == 1
        assert messages[0].function_call == function_call
        assert messages[0].function_name == "get_weather"

    async def test_get_messages(self):
        """Messages can be retrieved from memory."""
        memory = MemoryConversationMemory()

        # Add multiple messages
        await memory.add_message("thread-1", role="user", content="Hello")
        await asyncio.sleep(0.001)  # Ensure distinct timestamps
        await memory.add_message("thread-1", role="assistant", content="Hi there!")
        await asyncio.sleep(0.001)  # Ensure distinct timestamps
        await memory.add_message("thread-1", role="user", content="How are you?")

        messages = await memory.get_messages("thread-1")
        assert len(messages) == 3
        # Messages returned in DESC order (newest first)
        assert messages[0].content == "How are you?"
        assert messages[1].content == "Hi there!"
        assert messages[2].content == "Hello"

    async def test_get_messages_limit(self):
        """get_messages respects limit parameter."""
        memory = MemoryConversationMemory()

        # Add 5 messages
        for i in range(5):
            await memory.add_message("thread-1", role="user", content=f"Message {i}")

        messages = await memory.get_messages("thread-1", limit=3)
        assert len(messages) == 3

    async def test_get_messages_offset(self):
        """get_messages respects offset parameter."""
        memory = MemoryConversationMemory()

        # Add 5 messages
        for i in range(5):
            await memory.add_message("thread-1", role="user", content=f"Message {i}")
            await asyncio.sleep(0.001)  # Ensure distinct timestamps

        messages = await memory.get_messages("thread-1", offset=2, limit=2)
        assert len(messages) == 2
        # Messages in DESC order: 4, 3, [2, 1], 0
        assert messages[0].content == "Message 2"
        assert messages[1].content == "Message 1"

    async def test_get_messages_empty_thread(self):
        """get_messages returns empty list for non-existent thread."""
        memory = MemoryConversationMemory()

        messages = await memory.get_messages("nonexistent-thread")
        assert messages == []

    async def test_thread_isolation(self):
        """Messages in different threads are isolated."""
        memory = MemoryConversationMemory()

        await memory.add_message("thread-1", role="user", content="Thread 1 message")
        await memory.add_message("thread-2", role="user", content="Thread 2 message")

        thread1_messages = await memory.get_messages("thread-1")
        thread2_messages = await memory.get_messages("thread-2")

        assert len(thread1_messages) == 1
        assert len(thread2_messages) == 1
        assert thread1_messages[0].content == "Thread 1 message"
        assert thread2_messages[0].content == "Thread 2 message"

    async def test_get_user_messages(self):
        """User messages can be retrieved across all threads."""
        memory = MemoryConversationMemory()

        # Add messages for user-123 across different threads
        await memory.add_message("thread-1", user_id="user-123", role="user", content="Message 1")
        await asyncio.sleep(0.001)  # Ensure distinct timestamps
        await memory.add_message("thread-2", user_id="user-123", role="user", content="Message 2")
        await asyncio.sleep(0.001)  # Ensure distinct timestamps
        await memory.add_message("thread-3", user_id="user-456", role="user", content="Message 3")

        user_messages = await memory.get_user_messages("user-123")
        assert len(user_messages) == 2
        # Messages in DESC order (newest first)
        assert user_messages[0].content == "Message 2"
        assert user_messages[1].content == "Message 1"

    async def test_get_user_messages_limit(self):
        """get_user_messages respects limit parameter."""
        memory = MemoryConversationMemory()

        # Add 5 messages for user
        for i in range(5):
            await memory.add_message(f"thread-{i}", user_id="user-123", role="user", content=f"Message {i}")

        messages = await memory.get_user_messages("user-123", limit=3)
        assert len(messages) == 3

    async def test_search_messages_in_thread(self):
        """Messages can be searched within a thread."""
        memory = MemoryConversationMemory()

        await memory.add_message("thread-1", role="user", content="What's the weather like?")
        await memory.add_message("thread-1", role="assistant", content="The weather is sunny.")
        await memory.add_message("thread-1", role="user", content="Tell me a joke")

        results = await memory.search_messages("weather", thread_id="thread-1")
        assert len(results) == 2
        assert "weather" in results[0].content.lower()
        assert "weather" in results[1].content.lower()

    async def test_search_messages_for_user(self):
        """Messages can be searched for a specific user."""
        memory = MemoryConversationMemory()

        await memory.add_message("thread-1", user_id="user-123", role="user", content="weather today")
        await memory.add_message("thread-2", user_id="user-123", role="user", content="weather tomorrow")
        await memory.add_message("thread-3", user_id="user-456", role="user", content="weather")

        results = await memory.search_messages("weather", user_id="user-123")
        assert len(results) == 2

    async def test_search_messages_global(self):
        """Messages can be searched globally."""
        memory = MemoryConversationMemory()

        await memory.add_message("thread-1", role="user", content="Python programming")
        await memory.add_message("thread-2", role="user", content="Python snake")
        await memory.add_message("thread-3", role="user", content="JavaScript")

        results = await memory.search_messages("Python")
        assert len(results) == 2

    async def test_delete_thread(self):
        """Thread messages can be deleted."""
        memory = MemoryConversationMemory()

        await memory.add_message("thread-1", role="user", content="Message 1")
        await memory.add_message("thread-1", role="user", content="Message 2")

        await memory.delete_thread("thread-1")

        messages = await memory.get_messages("thread-1")
        assert len(messages) == 0

    async def test_get_thread_stats(self):
        """Thread statistics can be retrieved."""
        memory = MemoryConversationMemory()

        await memory.add_message("thread-1", role="user", content="Message 1")
        await memory.add_message("thread-1", role="user", content="Message 2")
        await memory.add_message("thread-1", role="user", content="Message 3")

        stats = await memory.get_thread_stats("thread-1")
        assert stats["message_count"] == 3
        assert "first_message" in stats
        assert "last_message" in stats

    async def test_get_thread_stats_empty(self):
        """Thread stats return empty dict for non-existent thread."""
        memory = MemoryConversationMemory()

        stats = await memory.get_thread_stats("nonexistent-thread")
        assert stats['message_count'] == 0
        assert stats['thread_id'] == "nonexistent-thread"
