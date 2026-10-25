"""
Redis-based checkpoint storage for high-performance ephemeral checkpoints
"""

import json
from typing import Dict, List, Optional, Any
from datetime import datetime

from .core import (
    BaseCheckpointer,
    Checkpoint,
    CheckpointLoadError,
    CheckpointDeleteError,
    CheckpointStatus
)


class RedisCheckpointer(BaseCheckpointer):
    """
    Redis-based checkpoint storage.

    Optimized for high-performance, ephemeral checkpoints with automatic expiration.
    Perfect for temporary state management and high-throughput scenarios.

    Example:
        >>> import redis.asyncio as redis
        >>> redis_client = await redis.from_url("redis://localhost")
        >>> checkpointer = RedisCheckpointer(redis_client, ttl=86400)
            """

    def __init__(self, redis_client: Any, ttl: int = 86400):
        """
        Initialize with Redis client.

        Args:
            redis_client: redis.asyncio.Redis client instance
            ttl: Time to live in seconds (default: 86400 = 24 hours)

        Example:
            >>> import redis.asyncio as redis
            >>> client = await redis.from_url("redis://localhost:6379")
            >>> checkpointer = RedisCheckpointer(client, ttl=3600)
        """
        self.redis = redis_client
        self.ttl = ttl
    async def list_checkpoints(
        self,
        thread_id: str,
        pipeline_id: Optional[str] = None,
        limit: int = 10,
        offset: int = 0
    ) -> List[Checkpoint]:
        """List checkpoints for thread (most recent first)"""
        try:
            list_key = f"checkpoints:{thread_id}"

            # Get checkpoint IDs from sorted set (reverse order - newest first)
            checkpoint_ids = await self.redis.zrevrange(
                list_key,
                offset,
                offset + limit - 1
            )

            if not checkpoint_ids:
                return []

            # Load each checkpoint
            checkpoints = []
            for checkpoint_id in checkpoint_ids:
                if isinstance(checkpoint_id, bytes):
                    checkpoint_id = checkpoint_id.decode('utf-8')

                checkpoint_key = f"checkpoint:{thread_id}:{checkpoint_id}"
                checkpoint_json = await self.redis.get(checkpoint_key)

                if checkpoint_json:
                    if isinstance(checkpoint_json, bytes):
                        checkpoint_json = checkpoint_json.decode('utf-8')

                    checkpoint_data = json.loads(checkpoint_json)
                    checkpoints.append(self._dict_to_checkpoint(checkpoint_data))

            return checkpoints

        except Exception as e:
            raise CheckpointLoadError(f"Failed to list checkpoints from Redis: {e}")

    async def delete_checkpoints(
        self,
        thread_id: str,
        pipeline_id: Optional[str] = None,
        before: Optional[datetime] = None,
        keep_latest: int = 0,
    ) -> int:
        """Delete checkpoints"""
        try:
            list_key = f"checkpoints:{thread_id}"

            if keep_latest > 0:
                # Get all checkpoint IDs
                all_ids = await self.redis.zrevrange(list_key, 0, -1)

                # Delete all except latest N
                to_delete = all_ids[keep_latest:]
                deleted_count = 0

                for checkpoint_id in to_delete:
                    if isinstance(checkpoint_id, bytes):
                        checkpoint_id = checkpoint_id.decode('utf-8')

                    checkpoint_key = f"checkpoint:{thread_id}:{checkpoint_id}"
                    deleted = await self.redis.delete(checkpoint_key)
                    if deleted:
                        deleted_count += 1
                        await self.redis.zrem(list_key, checkpoint_id)

                return deleted_count

            elif before:
                # Delete checkpoints before timestamp
                before_timestamp = before.timestamp()

                # Get checkpoint IDs with score < before_timestamp
                checkpoint_ids = await self.redis.zrangebyscore(
                    list_key,
                    '-inf',
                    before_timestamp
                )

                deleted_count = 0
                for checkpoint_id in checkpoint_ids:
                    if isinstance(checkpoint_id, bytes):
                        checkpoint_id = checkpoint_id.decode('utf-8')

                    checkpoint_key = f"checkpoint:{thread_id}:{checkpoint_id}"
                    deleted = await self.redis.delete(checkpoint_key)
                    if deleted:
                        deleted_count += 1
                        await self.redis.zrem(list_key, checkpoint_id)

                return deleted_count

            else:
                # Delete all checkpoints for thread
                all_ids = await self.redis.zrange(list_key, 0, -1)
                deleted_count = 0

                for checkpoint_id in all_ids:
                    if isinstance(checkpoint_id, bytes):
                        checkpoint_id = checkpoint_id.decode('utf-8')

                    checkpoint_key = f"checkpoint:{thread_id}:{checkpoint_id}"
                    deleted = await self.redis.delete(checkpoint_key)
                    if deleted:
                        deleted_count += 1

                # Delete the list and latest pointer
                await self.redis.delete(list_key)
                await self.redis.delete(f"checkpoint:{thread_id}:latest")

                return deleted_count

        except Exception as e:
            raise CheckpointDeleteError(f"Failed to delete checkpoints from Redis: {e}")

    async def get_checkpoint_stats(
        self,
        thread_id: Optional[str] = None
    ) -> Dict[str, Any]:
        """Get checkpoint statistics"""
        try:
            if thread_id:
                # Stats for specific thread
                list_key = f"checkpoints:{thread_id}"
                total = await self.redis.zcard(list_key)

                if total == 0:
                    return {'total_checkpoints': 0, 'thread_id': thread_id}

                # Get oldest and newest timestamps
                oldest_data = await self.redis.zrange(list_key, 0, 0, withscores=True)
                newest_data = await self.redis.zrevrange(list_key, 0, 0, withscores=True)

                oldest_timestamp = oldest_data[0][1] if oldest_data else None
                newest_timestamp = newest_data[0][1] if newest_data else None

                return {
                    'total_checkpoints': total,
                    'oldest_checkpoint': datetime.fromtimestamp(oldest_timestamp) if oldest_timestamp else None,
                    'newest_checkpoint': datetime.fromtimestamp(newest_timestamp) if newest_timestamp else None,
                    'thread_id': thread_id
                }
            else:
                # Stats for all threads (scan for all checkpoint lists)
                cursor = 0
                threads = []
                total_checkpoints = 0

                # Scan for all checkpoint list keys
                while True:
                    cursor, keys = await self.redis.scan(cursor, match="checkpoints:*", count=100)

                    for key in keys:
                        if isinstance(key, bytes):
                            key = key.decode('utf-8')

                        # Extract thread_id from key
                        thread_id_part = key.replace('checkpoints:', '')
                        threads.append(thread_id_part)

                        # Count checkpoints in this thread
                        count = await self.redis.zcard(key)
                        total_checkpoints += count

                    if cursor == 0:
                        break

                if total_checkpoints == 0:
                    return {'total_checkpoints': 0, 'threads': []}

                return {
                    'total_checkpoints': total_checkpoints,
                    'threads': threads
                }

        except Exception:
            return {}

    async def close(self) -> None:
        """Close Redis connection"""
        if self.redis:
            await self.redis.close()

    def _dict_to_checkpoint(self, data: Dict[str, Any]) -> Checkpoint:
        """Convert dictionary to Checkpoint object"""
        return Checkpoint(
            checkpoint_id=data['checkpoint_id'],
            thread_id=data['thread_id'],
            pipeline_id=data['pipeline_id'],
            pipeline_version=data.get('pipeline_version'),
            step_id=data['step_id'],
            step_index=data['step_index'],
            step_name=data.get('step_name', data['step_id']),
            timestamp=datetime.fromisoformat(data['timestamp']),
            state=data.get('state', {}),
            metadata=data.get('metadata', {}),
            status=CheckpointStatus(data.get('status', 'completed')),
            parent_checkpoint_id=data.get('parent_checkpoint_id')
        )
