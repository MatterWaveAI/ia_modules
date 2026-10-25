"""Memory service for conversation history and agent memory"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class MemoryService:
    """Service for memory management using ia_modules memory backends"""

    def __init__(self, memory_backend=None):
        """
        Initialize memory service
        
        Args:
            memory_backend: MemoryBackend instance from ia_modules (Redis or SQL)
        """
        self.memory = memory_backend
        logger.info(f"Memory service initialized with {type(memory_backend).__name__ if memory_backend else 'no backend'}")

    async def get_conversation_history(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get conversation history for a session
        
        Args:
            session_id: Session/execution ID
            limit: Maximum number of messages to return
            
        Returns:
            List of message dictionaries
        """
        if not self.memory:
            logger.warning("No memory backend available")
            return []

        try:
            messages = await self._get_messages_from_backend(session_id, limit)
            
            # Format messages for API response
            formatted = []
            for msg in messages:
                formatted.append({
                    "role": msg.get("role", "user"),
                    "content": msg.get("content", ""),
                    "timestamp": msg.get("timestamp"),
                    "metadata": msg.get("metadata", {})
                })
            
            logger.info(f"Retrieved {len(formatted)} messages for session {session_id}")
            return formatted

        except Exception as e:
            logger.error(f"Error retrieving conversation history: {e}", exc_info=True)
            return []

    async def search_memory(
        self,
        query: str,
        session_id: Optional[str] = None,
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """
        Search memory by semantic similarity or keyword
        
        Args:
            query: Search query
            session_id: Optional session ID to filter by
            limit: Maximum number of results
            
        Returns:
            List of matching messages
        """
        if not self.memory:
            logger.warning("No memory backend available")
            return []

        try:
            # Try semantic search if available
            if hasattr(self.memory, 'search'):
                results = await self.memory.search(query, limit=limit)
            else:
                # Fallback to keyword search
                results = await self._keyword_search(query, session_id, limit)
            
            logger.info(f"Found {len(results)} results for query: {query}")
            return results

        except Exception as e:
            logger.error(f"Error searching memory: {e}", exc_info=True)
            return []

    async def get_memory_stats(self, session_id: str) -> Dict[str, Any]:
        """
        Get statistics about memory usage for a session
        
        Args:
            session_id: Session/execution ID
            
        Returns:
            Dictionary with stats (message_count, total_tokens, etc.)
        """
        if not self.memory:
            return {
                "message_count": 0,
                "total_tokens": 0,
                "first_message": None,
                "last_message": None
            }

        try:
            messages = await self._get_messages_from_backend(session_id, limit=1000)
            
            if not messages:
                return {
                    "message_count": 0,
                    "total_tokens": 0,
                    "first_message": None,
                    "last_message": None
                }

            total_tokens = 0
            for msg in messages:
                # Estimate tokens (rough: 1 token ≈ 4 chars)
                content = msg.get("content", "")
                total_tokens += len(content) // 4

            return {
                "message_count": len(messages),
                "total_tokens": total_tokens,
                "first_message": messages[0].get("timestamp") if messages else None,
                "last_message": messages[-1].get("timestamp") if messages else None,
                "avg_message_length": sum(len(m.get("content", "")) for m in messages) // len(messages) if messages else 0
            }

        except Exception as e:
            logger.error(f"Error getting memory stats: {e}", exc_info=True)
            return {
                "message_count": 0,
                "total_tokens": 0,
                "first_message": None,
                "last_message": None
            }

    async def _get_messages_from_backend(
        self,
        session_id: str,
        limit: int = 50
    ) -> List[Dict]:
        """Get messages from memory backend"""
        if hasattr(self.memory, 'get_messages'):
            messages = await self.memory.get_messages(session_id, limit=limit)
            return [self._message_to_dict(m) for m in messages]
        elif hasattr(self.memory, 'get_conversation'):
            conversation = await self.memory.get_conversation(session_id)
            return conversation.get("messages", [])[:limit]
        
        return []

    async def _keyword_search(
        self,
        query: str,
        session_id: Optional[str],
        limit: int
    ) -> List[Dict]:
        """Keyword search - not implemented without proper memory backend"""
        logger.warning("Keyword search not available without memory backend")
        return []

    def _message_to_dict(self, message) -> Dict:
        """Convert message object to dictionary"""
        if isinstance(message, dict):
            return message

        return {
            "role": getattr(message, "role", "user"),
            "content": getattr(message, "content", ""),
            "timestamp": getattr(message, "timestamp", None),
            "metadata": getattr(message, "metadata", {})
        }
