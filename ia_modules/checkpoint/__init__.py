"""
Checkpoint System for IA Modules

Provides persistent state management for pipeline executions,
enabling pause/resume, fault recovery, and human-in-the-loop workflows.
"""

from .core import Checkpoint, BaseCheckpointer, CheckpointError, CheckpointSaveError, CheckpointLoadError
from .memory import MemoryCheckpointer

__all__ = [
    'Checkpoint',
    'BaseCheckpointer',
    'CheckpointError',
    'CheckpointSaveError',
    'CheckpointLoadError',
    'MemoryCheckpointer',
]

# Optional backends (import only if dependencies available)
try:
    from .sql import SQLCheckpointer  # noqa: F401
    __all__.append('SQLCheckpointer')
except ImportError:
    pass

try:
    from .redis import RedisCheckpointer  # noqa: F401
    __all__.append('RedisCheckpointer')
except ImportError:
    pass
