"""
Unit tests for tool system.

Tests ToolDefinition and ToolRegistry.
"""
import pytest
from ia_modules.tools.core import (
    ToolDefinition,
    ToolRegistry,
    tool,
    function_tool,
    from_langchain_tool,
    from_openai_function,
    ToolAdapter
)


class TestToolDefinition:
    """Test ToolDefinition."""

    def test_tool_definition_creation(self):
        """ToolDefinition can be created."""
        async def dummy_func(param1: str) -> str:
            return f"Result: {param1}"

        tool = ToolDefinition(
            name="test_tool",
            description="Test tool",
            parameters={"param1": {"type": "string", "required": True}},
            function=dummy_func
        )

        assert tool.name == "test_tool"
        assert tool.description == "Test tool"
        assert not tool.requires_approval

    def test_validate_parameters_valid(self):
        """ToolDefinition validates correct parameters."""
        async def dummy_func(param1: str) -> str:
            return param1

        tool = ToolDefinition(
            name="test",
            description="Test",
            parameters={"param1": {"type": "string", "required": True}},
            function=dummy_func
        )

        is_valid, error = tool.validate_parameters({"param1": "value"})
        assert is_valid is True
        assert error is None

    def test_validate_parameters_missing_required(self):
        """ToolDefinition catches missing required parameters."""
        async def dummy_func(param1: str) -> str:
            return param1

        tool = ToolDefinition(
            name="test",
            description="Test",
            parameters={"param1": {"type": "string", "required": True}},
            function=dummy_func
        )

        is_valid, error = tool.validate_parameters({})
        assert is_valid is False
        assert "Missing required parameter" in error

    def test_validate_parameters_wrong_type(self):
        """ToolDefinition catches type errors."""
        async def dummy_func(param1: str) -> str:
            return param1

        tool = ToolDefinition(
            name="test",
            description="Test",
            parameters={"param1": {"type": "string"}},
            function=dummy_func
        )

        is_valid, error = tool.validate_parameters({"param1": 123})
        assert is_valid is False
        assert "must be string" in error


@pytest.mark.asyncio
class TestToolRegistry:
    """Test ToolRegistry."""

    async def test_registry_creation(self):
        """ToolRegistry can be created."""
        registry = ToolRegistry()

        assert len(registry.tools) > 0  # Has built-in tools

    async def test_register_tool(self):
        """Tools can be registered."""
        registry = ToolRegistry()

        async def custom_tool(param1: str) -> str:
            return f"Custom: {param1}"

        tool = ToolDefinition(
            name="custom",
            description="Custom tool",
            parameters={"param1": {"type": "string"}},
            function=custom_tool
        )

        registry.register(tool)

        assert "custom" in registry.tools

    async def test_unregister_tool(self):
        """Tools can be unregistered."""
        registry = ToolRegistry()

        async def custom_tool(param1: str) -> str:
            return param1

        tool = ToolDefinition(
            name="custom",
            description="Custom",
            parameters={},
            function=custom_tool
        )

        registry.register(tool)
        result = registry.unregister("custom")

        assert result is True
        assert "custom" not in registry.tools

    async def test_execute_tool(self):
        """Tools can be executed."""
        registry = ToolRegistry()

        # Use built-in echo tool
        result = await registry.execute("echo", {"message": "Hello"})

        assert result == "Hello"

    async def test_execute_calculator(self):
        """Built-in calculator works."""
        registry = ToolRegistry()

        result = await registry.execute("calculator", {"expression": "2+2"})

        assert result == 4.0

    async def test_execute_calculator_complex(self):
        """Calculator handles complex expressions."""
        registry = ToolRegistry()

        result = await registry.execute("calculator", {"expression": "pow(2,3)+5"})

        assert result == 13.0

    async def test_execute_unknown_tool(self):
        """Executing unknown tool raises error."""
        registry = ToolRegistry()

        with pytest.raises(ValueError, match="Unknown tool"):
            await registry.execute("nonexistent", {})

    async def test_execute_invalid_parameters(self):
        """Invalid parameters raise error."""
        registry = ToolRegistry()

        with pytest.raises(ValueError, match="Invalid parameters"):
            await registry.execute("echo", {})  # Missing required 'message'

    async def test_list_tools(self):
        """Registry can list all tools."""
        registry = ToolRegistry()

        tools = registry.list_tools()

        assert len(tools) > 0
        assert any(t["name"] == "calculator" for t in tools)
        assert any(t["name"] == "echo" for t in tools)

    async def test_get_tool(self):
        """Registry can get tool definition."""
        registry = ToolRegistry()

        tool = registry.get_tool("calculator")

        assert tool is not None
        assert tool.name == "calculator"

    async def test_get_nonexistent_tool(self):
        """Getting nonexistent tool returns None."""
        registry = ToolRegistry()

        tool = registry.get_tool("nonexistent")

        assert tool is None

    async def test_execution_log(self):
        """Registry logs tool executions."""
        registry = ToolRegistry()

        await registry.execute("echo", {"message": "test"})

        log = registry.get_execution_log()

        assert len(log) > 0
        assert log[-1]["tool"] == "echo"
        assert log[-1]["success"] is True

    async def test_execution_log_error(self):
        """Registry logs execution errors."""
        registry = ToolRegistry()

        try:
            await registry.execute("calculator", {"expression": "invalid"})
        except ValueError:
            pass

        log = registry.get_execution_log()

        assert any(entry["tool"] == "calculator" and not entry["success"] for entry in log)

    async def test_registry_repr(self):
        """Registry has useful repr."""
        registry = ToolRegistry()

        repr_str = repr(registry)

        assert "ToolRegistry" in repr_str
        assert "tools=" in repr_str


@pytest.mark.asyncio
class TestToolDecorators:
    """Test tool decorators."""

    async def test_tool_decorator_basic(self):
        """@tool decorator creates tool definition."""
        @tool(name="my_tool", description="My custom tool")
        async def my_tool(message: str) -> str:
            return f"Processed: {message}"

        assert hasattr(my_tool, "_tool_definition")
        assert my_tool._tool_definition.name == "my_tool"
        assert my_tool._tool_definition.description == "My custom tool"

    async def test_tool_decorator_auto_name(self):
        """@tool decorator uses function name if name not provided."""
        @tool(description="Test tool")
        async def custom_function(value: int) -> int:
            return value * 2

        assert custom_function._tool_definition.name == "custom_function"

    async def test_tool_decorator_auto_description(self):
        """@tool decorator uses docstring if description not provided."""
        @tool()
        async def documented_tool(x: str) -> str:
            """This is a documented tool."""
            return x

        assert "This is a documented tool" in documented_tool._tool_definition.description

    async def test_tool_decorator_parameter_extraction(self):
        """@tool decorator extracts parameters from signature."""
        @tool()
        async def multi_param_tool(name: str, age: int, score: float) -> str:
            return f"{name}: {age}, {score}"

        params = multi_param_tool._tool_definition.parameters
        assert "name" in params
        assert "age" in params
        assert "score" in params
        assert params["name"]["type"] == "string"
        assert params["age"]["type"] == "integer"
        assert params["score"]["type"] == "number"

    async def test_tool_decorator_required_parameters(self):
        """@tool decorator marks parameters without defaults as required."""
        @tool()
        async def param_tool(required: str, optional: str = "default") -> str:
            return f"{required} {optional}"

        params = param_tool._tool_definition.parameters
        assert params["required"]["required"] is True
        assert params["optional"]["required"] is False

    async def test_tool_decorator_auto_register(self):
        """@tool decorator can auto-register with registry."""
        registry = ToolRegistry()

        @tool(name="auto_registered", registry=registry)
        async def auto_tool(msg: str) -> str:
            return msg

        assert "auto_registered" in registry.tools

    async def test_tool_decorator_requires_approval(self):
        """@tool decorator supports requires_approval flag."""
        @tool(requires_approval=True)
        async def dangerous_tool(action: str) -> bool:
            return True

        assert dangerous_tool._tool_definition.requires_approval is True

    async def test_function_tool_decorator(self):
        """@function_tool is a simple decorator."""
        @function_tool
        async def simple_tool(text: str) -> str:
            """Simple tool for testing."""
            return text.upper()

        assert hasattr(simple_tool, "_tool_definition")
        assert simple_tool._tool_definition.name == "simple_tool"
        assert "Simple tool for testing" in simple_tool._tool_definition.description

    async def test_decorated_tool_execution(self):
        """Decorated tool can be executed normally."""
        @tool()
        async def executable_tool(value: int) -> int:
            return value + 10

        result = await executable_tool(5)
        assert result == 15

    async def test_decorated_tool_registry_execution(self):
        """Decorated tool can be executed via registry."""
        registry = ToolRegistry()

        @tool(name="registry_tool", registry=registry)
        async def registry_tool(x: int, y: int) -> int:
            return x + y

        result = await registry.execute("registry_tool", {"x": 3, "y": 7})
        assert result == 10


@pytest.mark.asyncio
class TestToolAdapters:
    """Test tool adapters for external frameworks."""

    async def test_from_openai_function(self):
        """Can convert OpenAI function schema to ToolDefinition."""
        schema = {
            "name": "get_weather",
            "description": "Get current weather",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {
                        "type": "string",
                        "description": "City name"
                    },
                    "unit": {
                        "type": "string",
                        "description": "Temperature unit"
                    }
                },
                "required": ["location"]
            }
        }

        async def get_weather_impl(location: str, unit: str = "celsius") -> str:
            return f"Weather in {location}: 20°{unit[0].upper()}"

        tool_def = from_openai_function(schema, get_weather_impl)

        assert tool_def.name == "get_weather"
        assert tool_def.description == "Get current weather"
        assert "location" in tool_def.parameters
        assert "unit" in tool_def.parameters
        assert tool_def.parameters["location"]["required"] is True
        assert tool_def.parameters["unit"]["required"] is False
        assert tool_def.metadata["source"] == "openai"

    async def test_from_openai_function_execution(self):
        """OpenAI function can be executed."""
        schema = {
            "name": "add",
            "description": "Add two numbers",
            "parameters": {
                "type": "object",
                "properties": {
                    "a": {"type": "number"},
                    "b": {"type": "number"}
                },
                "required": ["a", "b"]
            }
        }

        async def add_impl(a: int, b: int) -> int:
            return a + b

        tool_def = from_openai_function(schema, add_impl)
        result = await tool_def.function(a=5, b=3)

        assert result == 8

    async def test_from_langchain_tool_mock(self):
        """Can convert mock LangChain tool to ToolDefinition."""
        # Mock LangChain tool structure
        class MockLangChainTool:
            name = "search"
            description = "Search the web"
            args_schema = None

            async def _arun(self, query: str) -> str:
                return f"Search results for: {query}"

        lc_tool = MockLangChainTool()
        tool_def = from_langchain_tool(lc_tool)

        assert tool_def.name == "search"
        assert tool_def.description == "Search the web"
        assert "query" in tool_def.parameters  # Fallback parameter
        assert tool_def.metadata["source"] == "langchain"

    async def test_from_langchain_tool_execution(self):
        """LangChain tool can be executed."""
        class MockLangChainTool:
            name = "echo"
            description = "Echo input"

            async def _arun(self, query: str) -> str:
                return f"Echo: {query}"

        lc_tool = MockLangChainTool()
        tool_def = from_langchain_tool(lc_tool)
        result = await tool_def.function(query="test")

        assert result == "Echo: test"

    async def test_from_langchain_tool_with_schema(self):
        """LangChain tool with args_schema extracts parameters."""
        # Mock Pydantic schema
        class MockArgsSchema:
            @staticmethod
            def schema():
                return {
                    "properties": {
                        "city": {
                            "type": "string",
                            "description": "City name"
                        },
                        "country": {
                            "type": "string",
                            "description": "Country code"
                        }
                    },
                    "required": ["city"]
                }

        class MockLangChainTool:
            name = "geocode"
            description = "Get coordinates"
            args_schema = MockArgsSchema

            async def _arun(self, city: str, country: str = "US") -> str:
                return f"{city}, {country}"

        lc_tool = MockLangChainTool()
        tool_def = from_langchain_tool(lc_tool)

        assert "city" in tool_def.parameters
        assert "country" in tool_def.parameters
        assert tool_def.parameters["city"]["required"] is True
        assert tool_def.parameters["country"]["required"] is False

    async def test_tool_adapter_add_openai_function(self):
        """ToolAdapter can add OpenAI function."""
        registry = ToolRegistry()
        adapter = ToolAdapter(registry)

        schema = {
            "name": "multiply",
            "description": "Multiply numbers",
            "parameters": {
                "type": "object",
                "properties": {
                    "x": {"type": "number"},
                    "y": {"type": "number"}
                },
                "required": ["x", "y"]
            }
        }

        async def multiply(x: int, y: int) -> int:
            return x * y

        tool_def = adapter.add_openai_function(schema, multiply)

        assert "multiply" in registry.tools
        assert tool_def.name == "multiply"

    async def test_tool_adapter_add_multiple_openai_functions(self):
        """ToolAdapter can add multiple OpenAI functions."""
        registry = ToolRegistry()
        adapter = ToolAdapter(registry)

        async def func1(x: int) -> int:
            return x

        async def func2(y: int) -> int:
            return y

        schemas = [
            ({"name": "func1", "parameters": {"type": "object", "properties": {}}}, func1),
            ({"name": "func2", "parameters": {"type": "object", "properties": {}}}, func2)
        ]

        tools = adapter.add_openai_functions(schemas)

        assert len(tools) == 2
        assert "func1" in registry.tools
        assert "func2" in registry.tools

    async def test_tool_adapter_add_langchain_tool(self):
        """ToolAdapter can add LangChain tool."""
        registry = ToolRegistry()
        adapter = ToolAdapter(registry)

        class MockTool:
            name = "test_tool"
            description = "Test"

            async def _arun(self, query: str) -> str:
                return query

        mock_tool = MockTool()
        tool_def = adapter.add_langchain_tool(mock_tool)

        assert "test_tool" in registry.tools
        assert tool_def.name == "test_tool"

    async def test_tool_adapter_add_multiple_langchain_tools(self):
        """ToolAdapter can add multiple LangChain tools."""
        registry = ToolRegistry()
        adapter = ToolAdapter(registry)

        class MockTool1:
            name = "tool1"
            description = "Tool 1"

            async def _arun(self, query: str) -> str:
                return "1"

        class MockTool2:
            name = "tool2"
            description = "Tool 2"

            async def _arun(self, query: str) -> str:
                return "2"

        tools = adapter.add_langchain_tools([MockTool1(), MockTool2()])

        assert len(tools) == 2
        assert "tool1" in registry.tools
        assert "tool2" in registry.tools
