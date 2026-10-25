"""
Memory System for IA Modules

Provides conversation memory with pluggable backends:
- In-memory (default)
- SQL (PostgreSQL, SQLite, MySQL, DuckDB)
- Redis (with TTL)
"""

from .core import ConversationMemory, Message, MessageRole
from .memory_backend import MemoryConversationMemory

__all__ = [
    'ConversationMemory',
    'Message',
    'MessageRole',
    'MemoryConversationMemory',
]

# Optional backends
try:
    from .sql import SQLConversationMemory  # noqa: F401
    __all__.append('SQLConversationMemory')
except ImportError:
    pass

try:
    from .redis import RedisConversationMemory  # noqa: F401
    __all__.append('RedisConversationMemory')
except ImportError:
    pass
