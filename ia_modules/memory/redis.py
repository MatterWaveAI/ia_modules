"""
Redis-based conversation memory for high-performance ephemeral storage
"""

import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from .core import ConversationMemory, Message, MessageRole


class RedisConversationMemory(ConversationMemory):
    """
    Redis-based conversation memory.

    High-performance ephemeral storage with automatic TTL.
    """

    def __init__(self, redis_client: Any, ttl: int = 604800):  # 7 days default
        self.redis = redis_client
        self.ttl = ttl
    async def get_user_messages(
        self,
        user_id: str,
        limit: int = 100,
        offset: int = 0
    ) -> List[Message]:
        """Get all messages for user"""
        user_key = f"user:{user_id}:messages"

        # Get message IDs
        message_ids = await self.redis.zrevrange(user_key, offset, offset + limit - 1)

        if not message_ids:
            return []

        messages = []
        for message_id in message_ids:
            if isinstance(message_id, bytes):
                message_id = message_id.decode('utf-8')

            # Find the thread for this message (scan user's threads)
            cursor = 0
            thread_id = None

            while True:
                cursor, keys = await self.redis.scan(cursor, match=f"user:{user_id}:thread:*", count=100)

                for key in keys:
                    if isinstance(key, bytes):
                        key = key.decode('utf-8')

                    is_member = await self.redis.sismember(key, message_id)
                    if is_member:
                        thread_id = key.split(':')[-1]
                        break

                if thread_id or cursor == 0:
                    break

            if thread_id:
                message_key = f"message:{thread_id}:{message_id}"
                message_json = await self.redis.get(message_key)

                if message_json:
                    if isinstance(message_json, bytes):
                        message_json = message_json.decode('utf-8')

                    message_data = json.loads(message_json)
                    messages.append(self._dict_to_message(message_data))

        return messages

    async def search_messages(
        self,
        query: str,
        thread_id: Optional[str] = None,
        user_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Message]:
        """Search messages by content (simple implementation)"""
        query_lower = query.lower()
        matches = []

        if thread_id:
            # Search in specific thread
            messages = await self.get_messages(thread_id, limit=1000)
            for msg in messages:
                if query_lower in msg.content.lower():
                    if user_id is None or msg.user_id == user_id:
                        matches.append(msg)
                        if len(matches) >= limit:
                            break
        elif user_id:
            # Search user's messages
            messages = await self.get_user_messages(user_id, limit=1000)
            for msg in messages:
                if query_lower in msg.content.lower():
                    matches.append(msg)
                    if len(matches) >= limit:
                        break
        else:
            # Search all threads (expensive - scan all message keys)
            cursor = 0
            while len(matches) < limit:
                cursor, keys = await self.redis.scan(cursor, match="message:*", count=100)

                for key in keys:
                    if isinstance(key, bytes):
                        key = key.decode('utf-8')

                    message_json = await self.redis.get(key)
                    if message_json:
                        if isinstance(message_json, bytes):
                            message_json = message_json.decode('utf-8')

                        message_data = json.loads(message_json)
                        if query_lower in message_data['content'].lower():
                            matches.append(self._dict_to_message(message_data))
                            if len(matches) >= limit:
                                break

                if cursor == 0:
                    break

        return matches[:limit]

    async def delete_thread(self, thread_id: str) -> int:
        """Delete all messages in thread"""
        thread_key = f"thread:{thread_id}"

        # Get all message IDs
        message_ids = await self.redis.zrange(thread_key, 0, -1)

        deleted_count = 0
        for message_id in message_ids:
            if isinstance(message_id, bytes):
                message_id = message_id.decode('utf-8')

            message_key = f"message:{thread_id}:{message_id}"
            deleted = await self.redis.delete(message_key)
            if deleted:
                deleted_count += 1

        # Delete thread key
        await self.redis.delete(thread_key)

        return deleted_count

    async def get_thread_stats(self, thread_id: str) -> Dict[str, Any]:
        """Get thread statistics"""
        thread_key = f"thread:{thread_id}"

        # Get message count
        count = await self.redis.zcard(thread_key)

        if count == 0:
            return {'message_count': 0, 'thread_id': thread_id}

        # Get timestamps
        oldest = await self.redis.zrange(thread_key, 0, 0, withscores=True)
        newest = await self.redis.zrevrange(thread_key, 0, 0, withscores=True)

        return {
            'message_count': count,
            'first_message': datetime.fromtimestamp(oldest[0][1]) if oldest else None,
            'last_message': datetime.fromtimestamp(newest[0][1]) if newest else None,
            'thread_id': thread_id
        }

    async def close(self) -> None:
        """Close Redis connection"""
        await self.redis.close()

    def _dict_to_message(self, data: Dict[str, Any]) -> Message:
        """Convert dictionary to Message"""
        return Message(
            message_id=data['message_id'],
            thread_id=data['thread_id'],
            user_id=data.get('user_id'),
            role=MessageRole(data['role']),
            content=data['content'],
            metadata=data.get('metadata', {}),
            timestamp=datetime.fromisoformat(data['timestamp']),
            function_call=data.get('function_call'),
            function_name=data.get('function_name')
        )
