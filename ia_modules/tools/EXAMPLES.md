# Advanced Tool System - Examples

This document provides examples of using the Advanced Tool/Function Calling system.

## Basic Usage

### 1. Simple Tool Execution

```python
import asyncio
from ia_modules.tools import AdvancedToolExecutor
from ia_modules.tools.builtin_tools import register_all_builtin_tools

async def main():
    # Initialize executor
    executor = AdvancedToolExecutor()

    # Register built-in tools
    register_all_builtin_tools(executor.registry)

    # Execute a calculation
    result = await executor.execute_tool(
        "calculator",
        {"expression": "2 + 2 * 3"}
    )
    print(f"Result: {result}")

asyncio.run(main())
```

### 2. Tool with Error Handling

```python
import asyncio
from ia_modules.tools import AdvancedToolExecutor, RetryConfig
from ia_modules.tools.builtin_tools import register_all_builtin_tools

async def main():
    executor = AdvancedToolExecutor(
        default_retry_config=RetryConfig(max_attempts=3)
    )

    register_all_builtin_tools(executor.registry)

    # Execute with retry and caching
    result = await executor.execute_tool(
        "web_search",
        {"query": "artificial intelligence", "max_results": 5},
        retry=True,
        cache_ttl=3600  # Cache for 1 hour
    )
    print(f"Found {result['count']} results")

asyncio.run(main())
```

### 3. Task Planning and Execution

```python
import asyncio
from ia_modules.tools import AdvancedToolExecutor
from ia_modules.tools.builtin_tools import register_all_builtin_tools

async def main():
    executor = AdvancedToolExecutor()
    register_all_builtin_tools(executor.registry)

    # Execute high-level task with automatic planning
    result = await executor.execute_task(
        "Search for AI trends and calculate statistics on results",
        requirements=["web_search", "calculation"],
        context={"query": "AI trends 2024"}
    )

    print(f"Success: {result['success']}")
    print(f"Steps executed: {result['steps_executed']}")
    print(f"Plan complexity: {result['plan']['complexity']}")

asyncio.run(main())
```

## Advanced Features

### 4. Tool Chaining

```python
import asyncio
from ia_modules.tools import AdvancedToolExecutor, ChainBuilder
from ia_modules.tools.builtin_tools import register_all_builtin_tools

async def main():
    executor = AdvancedToolExecutor()
    register_all_builtin_tools(executor.registry)

    # Build a chain
    chain = (ChainBuilder(executor._create_tool_executor())
        .step("web_search", {"query": "query_input"}, "search_results")
        .step("calculator", {"expression": "calculation_input"}, "calc_result")
        .build())

    # Execute chain
    result = await chain.execute({
        "query_input": "Python tutorials",
        "calculation_input": "10 + 20"
    })

    print(f"Chain success: {result.success}")
    print(f"Results: {result.context}")

asyncio.run(main())
```

### 5. Parallel Execution

```python
import asyncio
from ia_modules.tools import AdvancedToolExecutor
from ia_modules.tools.builtin_tools import register_all_builtin_tools

async def main():
    executor = AdvancedToolExecutor(max_concurrent=5)
    register_all_builtin_tools(executor.registry)

    # Execute multiple tools in parallel
    tasks = [
        ("calculator", {"expression": "2 + 2"}),
        ("calculator", {"expression": "3 * 3"}),
        ("calculator", {"expression": "10 / 2"}),
        ("web_search", {"query": "Python", "max_results": 3}),
        ("web_search", {"query": "JavaScript", "max_results": 3}),
    ]

    results = await executor.execute_parallel(tasks)

    for task_id, result in results.items():
        print(f"{task_id}: {result}")

asyncio.run(main())
```

### 6. Circuit Breaker Pattern

```python
import asyncio
from ia_modules.tools import (
    AdvancedToolExecutor,
    CircuitBreakerConfig,
    CircuitBreakerError
)
from ia_modules.tools.builtin_tools import register_all_builtin_tools

async def main():
    executor = AdvancedToolExecutor(
        default_circuit_breaker_config=CircuitBreakerConfig(
            failure_threshold=3,
            timeout=60.0
        )
    )

    register_all_builtin_tools(executor.registry)

    try:
        result = await executor.execute_tool(
            "api_caller",
            {
                "method": "GET",
                "url": "https://api.example.com/data"
            },
            use_circuit_breaker=True
        )
        print(f"Success: {result}")
    except CircuitBreakerError as e:
        print(f"Circuit breaker open: {e}")

asyncio.run(main())
```

### 7. Custom Tool Registration

```python
import asyncio
from ia_modules.tools import AdvancedToolExecutor, ToolDefinition

async def my_custom_tool(name: str, age: int) -> str:
    """Custom greeting tool."""
    return f"Hello, {name}! You are {age} years old."

async def main():
    executor = AdvancedToolExecutor()

    # Create and register custom tool
    tool_def = ToolDefinition(
        name="greeter",
        description="Generate a personalized greeting",
        parameters={
            "name": {"type": "string", "required": True},
            "age": {"type": "integer", "required": True}
        },
        function=my_custom_tool
    )

    executor.register_tool(
        tool_def,
        version="1.0.0",
        capabilities=["greeting", "personalization"]
    )

    # Use the tool
    result = await executor.execute_tool(
        "greeter",
        {"name": "Alice", "age": 30}
    )
    print(result)

asyncio.run(main())
```

### 8. Tool Versioning

```python
import asyncio
from ia_modules.tools import AdvancedToolExecutor, ToolDefinition

async def calculator_v1(expression: str) -> float:
    """Simple calculator v1."""
    return eval(expression)

async def calculator_v2(expression: str, precision: int = 2) -> float:
    """Enhanced calculator v2 with precision."""
    result = eval(expression)
    return round(result, precision)

async def main():
    executor = AdvancedToolExecutor()

    # Register v1
    tool_v1 = ToolDefinition(
        name="calculator",
        description="Calculator v1",
        parameters={"expression": {"type": "string", "required": True}},
        function=calculator_v1
    )
    executor.register_tool(tool_v1, version="1.0.0")

    # Register v2
    tool_v2 = ToolDefinition(
        name="calculator",
        description="Calculator v2 with precision",
        parameters={
            "expression": {"type": "string", "required": True},
            "precision": {"type": "integer", "required": False}
        },
        function=calculator_v2
    )
    executor.register_tool(tool_v2, version="2.0.0", set_as_default=True)

    # Use default version (2.0.0)
    result = await executor.execute_tool(
        "calculator",
        {"expression": "10 / 3", "precision": 4}
    )
    print(f"v2.0.0 (default): {result}")

    # Use specific version (1.0.0)
    result = await executor.execute_tool(
        "calculator",
        {"expression": "10 / 3"},
        version="1.0.0"
    )
    print(f"v1.0.0: {result}")

asyncio.run(main())
```

### 9. Statistics and Monitoring

```python
import asyncio
from ia_modules.tools import AdvancedToolExecutor
from ia_modules.tools.builtin_tools import register_all_builtin_tools

async def main():
    executor = AdvancedToolExecutor()
    register_all_builtin_tools(executor.registry)

    # Execute some tools
    await executor.execute_tool("calculator", {"expression": "1 + 1"})
    await executor.execute_tool("calculator", {"expression": "2 * 2"})
    await executor.execute_tool("web_search", {"query": "test"})

    # Get statistics
    stats = executor.get_statistics()

    print("Tool Statistics:")
    for tool_name, tool_stats in stats["registry"].items():
        print(f"\n{tool_name}:")
        print(f"  Total calls: {tool_stats['total_calls']}")
        print(f"  Successful: {tool_stats['successful_calls']}")
        print(f"  Failed: {tool_stats['failed_calls']}")
        print(f"  Avg duration: {tool_stats['total_duration'] / max(tool_stats['total_calls'], 1):.3f}s")

asyncio.run(main())
```

### 10. Complete Example - Multi-Agent Research Assistant

```python
import asyncio
from ia_modules.tools import (
    AdvancedToolExecutor,
    ChainBuilder,
    RetryConfig,
    CircuitBreakerConfig
)
from ia_modules.tools.builtin_tools import register_all_builtin_tools

async def research_assistant(topic: str):
    """
    Complete research assistant that:
    1. Searches for information
    2. Processes results
    3. Generates summary statistics
    """
    executor = AdvancedToolExecutor(
        enable_caching=True,
        max_concurrent=5,
        default_retry_config=RetryConfig(max_attempts=3),
        default_circuit_breaker_config=CircuitBreakerConfig()
    )

    register_all_builtin_tools(executor.registry)

    # Build research chain
    chain = (ChainBuilder(executor._create_tool_executor())
        .step(
            "web_search",
            {"query": "topic", "max_results": "max_results"},
            "search_results"
        )
        .parallel([
            ("calculator", {"expression": "stat_calc"}, "statistics"),
            ("file_operations", {
                "operation": "op_type",
                "file_path": "output_path",
                "data": "search_results"
            }, "saved_results")
        ])
        .build())

    # Execute research
    result = await chain.execute({
        "topic": topic,
        "max_results": 10,
        "stat_calc": "10 * 2",  # Example calculation
        "op_type": "write_json",
        "output_path": f"research_{topic.replace(' ', '_')}.json"
    })

    return result

async def main():
    topic = "artificial intelligence trends"
    result = await research_assistant(topic)

    print(f"Research complete for: {topic}")
    print(f"Success: {result.success}")
    print(f"Steps executed: {result.steps_executed}")

    if result.errors:
        print(f"Errors: {result.errors}")

asyncio.run(main())
```

## Best Practices

1. **Always use error handling**: Enable retry and circuit breaker for production
2. **Cache expensive operations**: Use `cache_ttl` parameter for API calls
3. **Version your tools**: Use semantic versioning for tool updates
4. **Monitor execution**: Check statistics regularly to identify issues
5. **Use parallel execution**: Run independent tools concurrently for better performance
6. **Validate inputs**: Tools automatically validate parameters against schemas
7. **Plan complex workflows**: Use ToolPlanner for multi-step operations
8. **Chain related operations**: Use ToolChain for sequential processing

## Security Considerations

1. **Code Executor**: Requires approval by default, use with caution
2. **File Operations**: Requires approval, respects base path restrictions
3. **API Caller**: Supports rate limiting to prevent abuse
4. **Input Validation**: All tools validate inputs against parameter schemas
5. **Resource Limits**: Configure timeouts and concurrent execution limits
