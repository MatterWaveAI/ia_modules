"""
Advanced Tool System for Agent Grounding.

Provides comprehensive tool management, execution, and composition capabilities:
- Tool registry with versioning and capability indexing
- Intelligent planning and task decomposition
- Parallel execution with resource management
- Tool chaining for complex workflows
- Error handling (retry, circuit breaker, fallback)
- Built-in tools for common operations

Example:
    >>> from ia_modules.tools import AdvancedToolExecutor
    >>> from ia_modules.tools.builtin_tools import register_all_builtin_tools
    >>>
    >>> # Initialize executor
    >>> executor = AdvancedToolExecutor()
    >>>
    >>> # Register built-in tools
    >>> register_all_builtin_tools(executor.registry)
    >>>
    >>> # Execute a task
    >>> result = await executor.execute_task(
    ...     "Search for AI trends and calculate statistics"
    ... )
"""

# Core components
from .core import (
    ToolDefinition,
    ToolRegistry,
    tool,
    function_tool,
    from_langchain_tool,
    from_openai_function,
    ToolAdapter
)

# Advanced components
from .tool_registry import (
    AdvancedToolRegistry,
    ToolVersion,
    CacheEntry,
    ToolCapability
)

from .tool_planner import (
    ToolPlanner,
    Task,
    ExecutionPlan,
    ToolMatch,
    TaskComplexity
)

from .tool_chain import (
    ToolChain,
    ChainStep,
    ChainResult,
    ChainMode,
    ChainBuilder
)

from .parallel_executor import (
    ParallelExecutor,
    ExecutionTask,
    ExecutionStatus,
    ResourceLimits
)

from .error_handling import (
    RetryExecutor,
    RetryConfig,
    RetryStrategy,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
    FallbackExecutor,
    FallbackConfig,
    CompositeErrorHandler,
    with_retry,
    with_circuit_breaker,
    with_fallback
)

from .advanced_executor import AdvancedToolExecutor


__all__ = [
    # Core
    "ToolDefinition",
    "ToolRegistry",
    "tool",
    "function_tool",
    "from_langchain_tool",
    "from_openai_function",
    "ToolAdapter",

    # Registry
    "AdvancedToolRegistry",
    "ToolVersion",
    "CacheEntry",
    "ToolCapability",

    # Planner
    "ToolPlanner",
    "Task",
    "ExecutionPlan",
    "ToolMatch",
    "TaskComplexity",

    # Chain
    "ToolChain",
    "ChainStep",
    "ChainResult",
    "ChainMode",
    "ChainBuilder",

    # Parallel
    "ParallelExecutor",
    "ExecutionTask",
    "ExecutionStatus",
    "ResourceLimits",

    # Error handling
    "RetryExecutor",
    "RetryConfig",
    "RetryStrategy",
    "CircuitBreaker",
    "CircuitBreakerConfig",
    "CircuitBreakerError",
    "CircuitState",
    "FallbackExecutor",
    "FallbackConfig",
    "CompositeErrorHandler",
    "with_retry",
    "with_circuit_breaker",
    "with_fallback",

    # Advanced executor
    "AdvancedToolExecutor",
]


# Version info
__version__ = "1.0.0"
