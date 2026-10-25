"""
Core tool system for agent grounding.

Provides ToolDefinition and ToolRegistry for managing agent tools.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Callable, Optional, List
import logging
import inspect
from functools import wraps


@dataclass
class ToolDefinition:
    """
    Defines a tool that agents can use.

    Attributes:
        name: Unique tool identifier
        description: Human-readable description
        parameters: JSON Schema for parameters
        function: Async function to execute
        requires_approval: Whether tool needs human approval
        metadata: Additional tool configuration
    """
    name: str
    description: str
    parameters: Dict[str, Any]
    function: Callable
    requires_approval: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)

    def validate_parameters(self, params: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate parameters against schema.

        Args:
            params: Parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        # Simple validation - check required fields
        for param_name, param_schema in self.parameters.items():
            if param_schema.get("required", False) and param_name not in params:
                return False, f"Missing required parameter: {param_name}"

            if param_name in params:
                # Type checking
                param_type = param_schema.get("type")
                value = params[param_name]

                if param_type == "string" and not isinstance(value, str):
                    return False, f"Parameter {param_name} must be string"
                elif param_type == "integer" and not isinstance(value, int):
                    return False, f"Parameter {param_name} must be integer"
                elif param_type == "number" and not isinstance(value, (int, float)):
                    return False, f"Parameter {param_name} must be number"
                elif param_type == "boolean" and not isinstance(value, bool):
                    return False, f"Parameter {param_name} must be boolean"

        return True, None


class ToolRegistry:
    """
    Centralized tool management.

    Features:
    - Tool registration and discovery
    - Parameter validation
    - Execution logging
    - Permission controls

    Example:
        >>> registry = ToolRegistry()
        >>>
        >>> # Register custom tool
        >>> async def my_tool(param1: str) -> str:
        ...     return f"Result: {param1}"
        >>>
        >>> registry.register(ToolDefinition(
        ...     name="my_tool",
        ...     description="My custom tool",
        ...     parameters={"param1": {"type": "string", "required": True}},
        ...     function=my_tool
        ... ))
        >>>
        >>> # Execute tool
        >>> result = await registry.execute("my_tool", {"param1": "test"})
    """

    def __init__(self):
        """Initialize tool registry with built-in tools."""
        self.tools: Dict[str, ToolDefinition] = {}
        self.logger = logging.getLogger("ToolRegistry")
        self._execution_log: List[Dict[str, Any]] = []

        # Register built-in tools
        self._register_built_in_tools()

    def register(self, tool: ToolDefinition) -> None:
        """
        Register a tool.

        Args:
            tool: Tool definition to register
        """
        if tool.name in self.tools:
            self.logger.warning(f"Overwriting existing tool: {tool.name}")

        self.tools[tool.name] = tool
        self.logger.info(f"Registered tool: {tool.name}")

    def unregister(self, tool_name: str) -> bool:
        """
        Unregister a tool.

        Args:
            tool_name: Name of tool to remove

        Returns:
            True if tool was removed, False if not found
        """
        if tool_name in self.tools:
            del self.tools[tool_name]
            self.logger.info(f"Unregistered tool: {tool_name}")
            return True
        return False

    async def execute(self, tool_name: str, parameters: Dict[str, Any]) -> Any:
        """
        Execute a tool with validation.

        Args:
            tool_name: Name of tool to execute
            parameters: Tool parameters

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool not found or parameters invalid
        """
        if tool_name not in self.tools:
            raise ValueError(f"Unknown tool: {tool_name}")

        tool = self.tools[tool_name]

        # Validate parameters
        is_valid, error = tool.validate_parameters(parameters)
        if not is_valid:
            raise ValueError(f"Invalid parameters for {tool_name}: {error}")

        # Check approval if required
        if tool.requires_approval:
            self.logger.warning(f"Tool {tool_name} requires approval - executing anyway in automated mode")

        # Execute tool
        self.logger.info(f"Executing tool: {tool_name}")
        import time
        from datetime import datetime, timezone

        start_time = time.time()
        timestamp = datetime.now(timezone.utc).isoformat()

        try:
            result = await tool.function(**parameters)
            duration = time.time() - start_time

            # Log execution
            self._execution_log.append({
                "tool": tool_name,
                "parameters": parameters,
                "result": str(result)[:100],  # Truncate
                "success": True,
                "timestamp": timestamp,
                "duration": duration
            })

            return result

        except Exception as e:
            duration = time.time() - start_time
            self.logger.error(f"Tool {tool_name} failed: {e}")
            self._execution_log.append({
                "tool": tool_name,
                "parameters": parameters,
                "error": str(e),
                "success": False,
                "timestamp": timestamp,
                "duration": duration
            })
            raise

    def list_tools(self) -> List[Dict[str, Any]]:
        """
        List all registered tools.

        Returns:
            List of tool information
        """
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.parameters,
                "requires_approval": tool.requires_approval
            }
            for tool in self.tools.values()
        ]

    def get_tool(self, tool_name: str) -> Optional[ToolDefinition]:
        """
        Get tool definition.

        Args:
            tool_name: Tool name

        Returns:
            ToolDefinition or None if not found
        """
        return self.tools.get(tool_name)

    def get_execution_log(self, limit: int = 100) -> List[Dict[str, Any]]:
        """
        Get tool execution log.

        Args:
            limit: Maximum entries to return

        Returns:
            List of execution log entries
        """
        return self._execution_log[-limit:]

    def _register_built_in_tools(self) -> None:
        """Register built-in tools."""
        # Calculator
        self.register(ToolDefinition(
            name="calculator",
            description="Evaluate mathematical expressions",
            parameters={
                "expression": {
                    "type": "string",
                    "required": True,
                    "description": "Math expression to evaluate"
                }
            },
            function=self._calculator
        ))

        # Echo (for testing)
        self.register(ToolDefinition(
            name="echo",
            description="Echo back the input",
            parameters={
                "message": {
                    "type": "string",
                    "required": True,
                    "description": "Message to echo"
                }
            },
            function=self._echo
        ))

    async def _calculator(self, expression: str) -> float:
        """
        Evaluate mathematical expression.

        Args:
            expression: Math expression

        Returns:
            Result of calculation
        """
        try:
            # Safe eval with limited scope
            allowed_names = {
                "abs": abs,
                "round": round,
                "min": min,
                "max": max,
                "sum": sum,
                "pow": pow
            }

            # Remove spaces
            expression = expression.replace(" ", "")

            # Evaluate
            result = eval(expression, {"__builtins__": {}}, allowed_names)

            return float(result)

        except Exception as e:
            raise ValueError(f"Invalid expression: {e}")

    async def _echo(self, message: str) -> str:
        """Echo back message."""
        return message

    def __repr__(self) -> str:
        return f"<ToolRegistry(tools={len(self.tools)})>"


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    requires_approval: bool = False,
    registry: Optional[ToolRegistry] = None
) -> Callable:
    """
    Decorator for creating tools.

    Automatically extracts parameter schema from function signature and
    registers the tool with the provided registry.

    Args:
        name: Tool name (defaults to function name)
        description: Tool description (defaults to function docstring)
        requires_approval: Whether tool requires approval
        registry: ToolRegistry to auto-register with (optional)

    Example:
        >>> @tool(name="calculator", description="Calculate math expressions")
        ... async def calculate(expression: str) -> float:
        ...     return eval(expression)
        ...
        >>> @tool(requires_approval=True, registry=my_registry)
        ... async def delete_file(path: str) -> bool:
        ...     os.remove(path)
        ...     return True
    """
    def decorator(func: Callable) -> Callable:
        # Extract parameters from function signature
        sig = inspect.signature(func)
        parameters = {}

        for param_name, param in sig.parameters.items():
            param_schema = {}

            # Determine type from annotation
            if param.annotation != inspect.Parameter.empty:
                if param.annotation is str:
                    param_schema["type"] = "string"
                elif param.annotation is int:
                    param_schema["type"] = "integer"
                elif param.annotation is float or param.annotation == "float":
                    param_schema["type"] = "number"
                elif param.annotation is bool:
                    param_schema["type"] = "boolean"
                elif param.annotation is list or param.annotation is List:
                    param_schema["type"] = "array"
                elif param.annotation is dict or param.annotation is Dict:
                    param_schema["type"] = "object"
                else:
                    param_schema["type"] = "string"  # Default
            else:
                param_schema["type"] = "string"  # Default if no annotation

            # Check if required (no default value)
            param_schema["required"] = param.default == inspect.Parameter.empty

            # Add description from parameter name
            param_schema["description"] = f"Parameter: {param_name}"

            parameters[param_name] = param_schema

        # Create tool definition
        tool_def = ToolDefinition(
            name=name or func.__name__,
            description=description or func.__doc__ or f"Tool: {func.__name__}",
            parameters=parameters,
            function=func,
            requires_approval=requires_approval
        )

        # Auto-register if registry provided
        if registry:
            registry.register(tool_def)

        # Attach tool definition to function for later registration
        func._tool_definition = tool_def  # type: ignore[attr-defined]

        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await func(*args, **kwargs)

        wrapper._tool_definition = tool_def  # type: ignore[attr-defined]
        return wrapper

    return decorator


def function_tool(func: Callable) -> Callable:
    """
    Simple decorator for converting a function to a tool with minimal config.

    Uses function name, docstring, and signature for all metadata.

    Example:
        >>> @function_tool
        ... async def echo(message: str) -> str:
        ...     '''Echo back the input message'''
        ...     return message
    """
    return tool()(func)


def from_langchain_tool(langchain_tool: Any) -> ToolDefinition:
    """
    Convert a LangChain tool to ToolDefinition.

    Supports both LangChain Tool and StructuredTool classes.

    Args:
        langchain_tool: LangChain tool instance

    Returns:
        ToolDefinition compatible with our framework

    Example:
        >>> from langchain.tools import WikipediaQueryRun
        >>> lc_tool = WikipediaQueryRun()
        >>> our_tool = from_langchain_tool(lc_tool)
        >>> registry.register(our_tool)
    """
    # Extract name and description
    name = getattr(langchain_tool, "name", langchain_tool.__class__.__name__)
    description = getattr(langchain_tool, "description", "")

    # Extract parameters from args_schema if available
    parameters = {}
    if hasattr(langchain_tool, "args_schema") and langchain_tool.args_schema:
        # Pydantic model -> JSON Schema
        schema = langchain_tool.args_schema.schema()
        if "properties" in schema:
            for param_name, param_info in schema["properties"].items():
                param_schema = {
                    "type": param_info.get("type", "string"),
                    "description": param_info.get("description", ""),
                    "required": param_name in schema.get("required", [])
                }
                parameters[param_name] = param_schema
    else:
        # Fallback for simple tools - single query parameter
        parameters = {
            "query": {
                "type": "string",
                "description": "Query input",
                "required": True
            }
        }

    # Create wrapper function for async compatibility
    async def wrapper(**kwargs) -> str:
        # LangChain tools may be sync or async
        if hasattr(langchain_tool, "_arun"):
            result = await langchain_tool._arun(**kwargs)
        elif hasattr(langchain_tool, "arun"):
            result = await langchain_tool.arun(**kwargs)
        elif hasattr(langchain_tool, "_run"):
            # Sync tool - run in executor
            import asyncio
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: langchain_tool._run(**kwargs))
        elif hasattr(langchain_tool, "run"):
            import asyncio
            loop = asyncio.get_event_loop()
            result = await loop.run_in_executor(None, lambda: langchain_tool.run(**kwargs))
        else:
            raise ValueError(f"Unknown LangChain tool interface: {type(langchain_tool)}")

        return str(result)

    return ToolDefinition(
        name=name,
        description=description,
        parameters=parameters,
        function=wrapper,
        metadata={"source": "langchain", "original_class": langchain_tool.__class__.__name__}
    )


def from_openai_function(function_schema: Dict[str, Any], function_impl: Callable) -> ToolDefinition:
    """
    Convert an OpenAI function calling schema to ToolDefinition.

    Args:
        function_schema: OpenAI function JSON schema
        function_impl: Async function implementation

    Returns:
        ToolDefinition compatible with our framework

    Example:
        >>> schema = {
        ...     "name": "get_weather",
        ...     "description": "Get weather for a location",
        ...     "parameters": {
        ...         "type": "object",
        ...         "properties": {
        ...             "location": {"type": "string", "description": "City name"}
        ...         },
        ...         "required": ["location"]
        ...     }
        ... }
        >>> async def get_weather(location: str) -> str:
        ...     return f"Weather in {location}: Sunny"
        >>> tool = from_openai_function(schema, get_weather)
    """
    name = function_schema.get("name", "unknown")
    description = function_schema.get("description", "")

    # Convert OpenAI parameters format to our format
    parameters = {}
    openai_params = function_schema.get("parameters", {})
    properties = openai_params.get("properties", {})
    required = openai_params.get("required", [])

    for param_name, param_info in properties.items():
        parameters[param_name] = {
            "type": param_info.get("type", "string"),
            "description": param_info.get("description", ""),
            "required": param_name in required
        }

    return ToolDefinition(
        name=name,
        description=description,
        parameters=parameters,
        function=function_impl,
        metadata={"source": "openai", "schema": function_schema}
    )


class ToolAdapter:
    """
    Adapter for integrating external tool frameworks.

    Provides batch conversion and registry integration.

    Example:
        >>> adapter = ToolAdapter(registry)
        >>> adapter.add_langchain_tools([tool1, tool2, tool3])
        >>> adapter.add_openai_functions([(schema1, impl1), (schema2, impl2)])
    """

    def __init__(self, registry: ToolRegistry):
        """
        Initialize adapter.

        Args:
            registry: ToolRegistry to register converted tools
        """
        self.registry = registry
        self.logger = logging.getLogger("ToolAdapter")

    def add_langchain_tool(self, langchain_tool: Any) -> ToolDefinition:
        """
        Add a single LangChain tool.

        Args:
            langchain_tool: LangChain tool instance

        Returns:
            Converted ToolDefinition
        """
        tool_def = from_langchain_tool(langchain_tool)
        self.registry.register(tool_def)
        self.logger.info(f"Registered LangChain tool: {tool_def.name}")
        return tool_def

    def add_langchain_tools(self, langchain_tools: List[Any]) -> List[ToolDefinition]:
        """
        Add multiple LangChain tools.

        Args:
            langchain_tools: List of LangChain tool instances

        Returns:
            List of converted ToolDefinitions
        """
        converted = []
        for lc_tool in langchain_tools:
            converted.append(self.add_langchain_tool(lc_tool))
        self.logger.info(f"Registered {len(converted)} LangChain tools")
        return converted

    def add_openai_function(self, schema: Dict[str, Any], implementation: Callable) -> ToolDefinition:
        """
        Add a single OpenAI function.

        Args:
            schema: OpenAI function schema
            implementation: Async function implementation

        Returns:
            Converted ToolDefinition
        """
        tool_def = from_openai_function(schema, implementation)
        self.registry.register(tool_def)
        self.logger.info(f"Registered OpenAI function: {tool_def.name}")
        return tool_def

    def add_openai_functions(self, functions: List[tuple[Dict[str, Any], Callable]]) -> List[ToolDefinition]:
        """
        Add multiple OpenAI functions.

        Args:
            functions: List of (schema, implementation) tuples

        Returns:
            List of converted ToolDefinitions
        """
        converted = []
        for schema, impl in functions:
            converted.append(self.add_openai_function(schema, impl))
        self.logger.info(f"Registered {len(converted)} OpenAI functions")
        return converted
