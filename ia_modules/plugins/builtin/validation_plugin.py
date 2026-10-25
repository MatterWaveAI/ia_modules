"""
Validation Plugin

Plugins for data validation.
"""

from typing import Dict, Any, Optional
import re
from ..base import ValidatorPlugin, ConditionPlugin, PluginMetadata, PluginType


class SchemaValidator(ValidatorPlugin):
    """
    Validate data against schema

    Config:
        - schema: JSON schema definition
        - required_fields: List of required field names
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="schema_validator",
            version="1.0.0",
            author="IA Modules Team",
            description="Validate data against schema",
            plugin_type=PluginType.VALIDATOR,
            tags=["validation", "schema"]
        )

    async def validate(self, data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """Validate against schema"""
        required_fields = self.config.get('required_fields', [])

        # Check required fields
        missing_fields = []
        for field in required_fields:
            if field not in data:
                missing_fields.append(field)

        if missing_fields:
            return False, f"Missing required fields: {', '.join(missing_fields)}"

        # In real implementation, would use jsonschema
        return True, None


class EmailValidator(ConditionPlugin):
    """
    Validate email format

    Config:
        - field: Field name containing email (default: 'email')
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="email_validator",
            version="1.0.0",
            author="IA Modules Team",
            description="Validate email format",
            plugin_type=PluginType.CONDITION,
            tags=["validation", "email"]
        )

    async def evaluate(self, data: Dict[str, Any]) -> bool:
        """Validate email"""
        field = self.config.get('field', 'email')
        email = data.get(field, '')

        if not email:
            return False

        # Simple email regex
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return bool(re.match(pattern, email))


class RangeValidator(ConditionPlugin):
    """
    Validate numeric range

    Config:
        - field: Field name
        - min: Minimum value (optional)
        - max: Maximum value (optional)
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="range_validator",
            version="1.0.0",
            author="IA Modules Team",
            description="Validate numeric range",
            plugin_type=PluginType.CONDITION,
            tags=["validation", "numeric", "range"]
        )

    async def evaluate(self, data: Dict[str, Any]) -> bool:
        """Validate range"""
        field = self.config.get('field')
        min_value = self.config.get('min')
        max_value = self.config.get('max')

        if not field:
            return False

        value = data.get(field)

        if value is None:
            return False

        # Check range
        if min_value is not None and value < min_value:
            return False

        if max_value is not None and value > max_value:
            return False

        return True


class RegexValidator(ConditionPlugin):
    """
    Validate using regex pattern

    Config:
        - field: Field name
        - pattern: Regex pattern
    """

    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="regex_validator",
            version="1.0.0",
            author="IA Modules Team",
            description="Validate using regex",
            plugin_type=PluginType.CONDITION,
            tags=["validation", "regex"]
        )

    async def evaluate(self, data: Dict[str, Any]) -> bool:
        """Validate with regex"""
        field = self.config.get('field')
        pattern = self.config.get('pattern')

        if not field or not pattern:
            return False

        value = data.get(field, '')

        if not isinstance(value, str):
            return False

        try:
            return bool(re.match(pattern, value))
        except re.error:
            self.logger.error(f"Invalid regex pattern: {pattern}")
            return False
