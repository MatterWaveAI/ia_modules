"""
Edge case tests for tools/core.py to improve coverage
"""
import pytest
from typing import List, Dict, Any
from ia_modules.tools.core import (
    ToolDefinition,
    ToolRegistry,
    tool,
)


class TestToolDefinitionValidation:
    """Test edge cases in ToolDefinition validation"""

    def test_validate_params_integer_type_mismatch(self):
        """Test validation fails when integer parameter gets string"""
        async def dummy_func(count: int):
            return count

        tool_def = ToolDefinition(
            name="test_tool",
            description="Test",
            parameters={
                "count": {
                    "type": "integer",
                    "required": True,
                    "description": "Count parameter"
                }
            },
            function=dummy_func
        )

        # Pass string instead of integer
        valid, error = tool_def.validate_parameters({"count": "not_an_int"})

        assert valid is False
        assert "must be integer" in error

    def test_validate_params_number_type_mismatch(self):
        """Test validation fails when number parameter gets string"""
        async def dummy_func(value: float):
            return value

        tool_def = ToolDefinition(
            name="test_tool",
            description="Test",
            parameters={
                "value": {
                    "type": "number",
                    "required": True,
                    "description": "Numeric value"
                }
            },
            function=dummy_func
        )

        # Pass string instead of number
        valid, error = tool_def.validate_parameters({"value": "not_a_number"})

        assert valid is False
        assert "must be number" in error

    def test_validate_params_boolean_type_mismatch(self):
        """Test validation fails when boolean parameter gets non-boolean"""
        async def dummy_func(flag: bool):
            return flag

        tool_def = ToolDefinition(
            name="test_tool",
            description="Test",
            parameters={
                "flag": {
                    "type": "boolean",
                    "required": True,
                    "description": "Boolean flag"
                }
            },
            function=dummy_func
        )

        # Pass string instead of boolean
        valid, error = tool_def.validate_parameters({"flag": "true"})

        assert valid is False
        assert "must be boolean" in error


class TestToolRegistryEdgeCases:
    """Test edge cases in ToolRegistry"""

    def test_register_overwrites_existing_tool(self, caplog):
        """Test that registering same tool name logs warning"""
        registry = ToolRegistry()

        async def func1():
            return "first"

        async def func2():
            return "second"

        tool1 = ToolDefinition(
            name="duplicate_tool",
            description="First tool",
            parameters={},
            function=func1
        )
        tool2 = ToolDefinition(
            name="duplicate_tool",
            description="Second tool",
            parameters={},
            function=func2
        )

        # Register first tool
        registry.register(tool1)

        # Register second tool with same name
        registry.register(tool2)

        # Should log warning about overwriting
        assert "Overwriting existing tool" in caplog.text

    def test_unregister_nonexistent_tool(self):
        """Test unregister returns False for non-existent tool"""
        registry = ToolRegistry()

        # Try to unregister tool that doesn't exist
        result = registry.unregister("nonexistent_tool")

        assert result is False

    @pytest.mark.asyncio
    async def test_execute_with_approval_required(self, caplog):
        """Test executing tool that requires approval logs warning"""
        registry = ToolRegistry()

        # Define async tool function
        async def test_func(x: int) -> int:
            return x * 2

        tool_def = ToolDefinition(
            name="approval_tool",
            description="Tool requiring approval",
            parameters={
                "x": {
                    "type": "integer",
                    "required": True,
                    "description": "Input value"
                }
            },
            function=test_func,
            requires_approval=True
        )

        registry.register(tool_def)

        # Execute tool
        result = await registry.execute("approval_tool", {"x": 5})

        # Should log warning about approval
        assert "requires approval" in caplog.text
        assert result == 10


class TestToolDecoratorEdgeCases:
    """Test edge cases in @tool decorator"""

    def test_tool_decorator_with_float_annotation(self):
        """Test tool decorator handles float annotation"""
        @tool(name="float_tool", description="Uses float")
        async def process_float(value: float) -> float:
            return value * 2.0

        # Check parameter schema
        assert "value" in process_float._tool_definition.parameters
        assert process_float._tool_definition.parameters["value"]["type"] == "number"

    def test_tool_decorator_with_bool_annotation(self):
        """Test tool decorator handles bool annotation"""
        @tool(name="bool_tool", description="Uses boolean")
        async def process_bool(enabled: bool) -> str:
            return "yes" if enabled else "no"

        # Check parameter schema
        assert "enabled" in process_bool._tool_definition.parameters
        assert process_bool._tool_definition.parameters["enabled"]["type"] == "boolean"

    def test_tool_decorator_with_list_literal_annotation(self):
        """Test tool decorator handles list (lowercase) annotation"""
        @tool(name="list_tool", description="Uses list")
        async def process_list(items: list) -> int:
            return len(items)

        # Check parameter schema - list (lowercase) should be recognized
        assert "items" in process_list._tool_definition.parameters
        assert process_list._tool_definition.parameters["items"]["type"] == "array"

    def test_tool_decorator_with_dict_literal_annotation(self):
        """Test tool decorator handles dict (lowercase) annotation"""
        @tool(name="dict_tool", description="Uses dict")
        async def process_dict(data: dict) -> int:
            return len(data)

        # Check parameter schema - dict (lowercase) should be recognized
        assert "data" in process_dict._tool_definition.parameters
        assert process_dict._tool_definition.parameters["data"]["type"] == "object"

    def test_tool_decorator_with_generic_list_defaults_to_string(self):
        """Test tool decorator defaults List[T] to string (unsupported)"""
        @tool(name="generic_list_tool", description="Uses List[str]")
        async def process_generic_list(items: List[str]) -> int:
            return len(items)

        # Generic List[str] is not specifically handled, defaults to string
        assert "items" in process_generic_list._tool_definition.parameters
        assert process_generic_list._tool_definition.parameters["items"]["type"] == "string"

    def test_tool_decorator_with_generic_dict_defaults_to_string(self):
        """Test tool decorator defaults Dict[K,V] to string (unsupported)"""
        @tool(name="generic_dict_tool", description="Uses Dict[str, Any]")
        async def process_generic_dict(data: Dict[str, Any]) -> int:
            return len(data)

        # Generic Dict[str, Any] is not specifically handled, defaults to string
        assert "data" in process_generic_dict._tool_definition.parameters
        assert process_generic_dict._tool_definition.parameters["data"]["type"] == "string"

    def test_tool_decorator_with_no_annotation(self):
        """Test tool decorator defaults to string when no annotation"""
        @tool(name="no_annotation_tool", description="No type annotation")
        async def process_no_annotation(value) -> str:
            return str(value)

        # Check parameter schema - should default to string
        assert "value" in process_no_annotation._tool_definition.parameters
        assert process_no_annotation._tool_definition.parameters["value"]["type"] == "string"

    def test_tool_decorator_with_string_annotation(self):
        """Test tool decorator handles string annotation (as string literal)"""
        @tool(name="string_annotation_tool", description="Uses string annotation")
        async def process_string_annotation(value: "float") -> float:
            return float(value)

        # Check parameter schema - "float" as string should be recognized
        assert "value" in process_string_annotation._tool_definition.parameters
        assert process_string_annotation._tool_definition.parameters["value"]["type"] == "number"

    def test_tool_decorator_with_unknown_annotation(self):
        """Test tool decorator defaults to string for unknown types"""
        class CustomType:
            pass

        @tool(name="custom_type_tool", description="Uses custom type")
        async def process_custom(value: CustomType) -> str:
            return str(value)

        # Check parameter schema - unknown type should default to string
        assert "value" in process_custom._tool_definition.parameters
        assert process_custom._tool_definition.parameters["value"]["type"] == "string"

    def test_tool_decorator_required_vs_optional(self):
        """Test tool decorator marks parameters with defaults as not required"""
        @tool(name="optional_param_tool", description="Has optional param")
        async def process_optional(required: str, optional: str = "default") -> str:
            return f"{required}-{optional}"

        # Check required flags
        params = process_optional._tool_definition.parameters
        assert params["required"]["required"] is True
        assert params["optional"]["required"] is False
