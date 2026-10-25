# Plugin System Documentation

Extensible plugin architecture for custom conditions, steps, validators, and hooks.

## Table of Contents

- [Overview](#overview)
- [Plugin Types](#plugin-types)
- [Creating Plugins](#creating-plugins)
- [Plugin Registry](#plugin-registry)
- [Built-in Plugins](#built-in-plugins)
- [Using Plugins in Pipelines](#using-plugins-in-pipelines)
- [Testing Plugins](#testing-plugins)
- [Examples](#examples)

## Overview

The plugin system allows you to extend IA Modules with custom functionality:

- **ConditionPlugin**: Custom routing conditions
- **StepPlugin**: Custom pipeline steps
- **ValidatorPlugin**: Data validation logic
- **TransformPlugin**: Data transformers
- **HookPlugin**: Lifecycle event handlers

All plugins implement the `Plugin` base class and provide metadata about their capabilities.

## Plugin Types

### Base Plugin Interface

```python
from ia_modules.plugins.base import Plugin, PluginMetadata, PluginType

class MyPlugin(Plugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_plugin",
            version="1.0.0",
            description="My custom plugin",
            plugin_type=PluginType.CONDITION
        )
```

### ConditionPlugin

Custom conditions for pipeline routing:

```python
from ia_modules.plugins.base import ConditionPlugin, PluginMetadata, PluginType

class ThresholdCondition(ConditionPlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="threshold_condition",
            version="1.0.0",
            description="Check if value exceeds threshold",
            plugin_type=PluginType.CONDITION
        )

    async def evaluate(self, data: dict) -> bool:
        """
        Evaluate the condition.

        Args:
            data: Input data dict

        Returns:
            True if condition passes, False otherwise
        """
        value = data.get('value', 0)
        threshold = self.config.get('threshold', 10)
        return value > threshold
```

### StepPlugin

Custom processing steps:

```python
from ia_modules.plugins.base import StepPlugin, PluginMetadata, PluginType

class DataProcessorStep(StepPlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="data_processor",
            version="1.0.0",
            description="Process data",
            plugin_type=PluginType.STEP
        )

    async def execute(self, data: dict) -> dict:
        """
        Execute the step.

        Args:
            data: Input data dict

        Returns:
            Processed data dict
        """
        # Process data
        processed_data = data.copy()
        processed_data['processed'] = True
        return processed_data
```

### ValidatorPlugin

Data validation logic:

```python
from ia_modules.plugins.base import ValidatorPlugin, PluginMetadata, PluginType

class EmailValidator(ValidatorPlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="email_validator",
            version="1.0.0",
            description="Validate email format",
            plugin_type=PluginType.VALIDATOR
        )

    async def validate(self, data: dict) -> tuple[bool, Optional[str]]:
        """
        Validate data.

        Args:
            data: Data to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        import re

        email = data.get('email', '')
        pattern = r'^[\w\.-]+@[\w\.-]+\.\w+$'

        if not re.match(pattern, email):
            return False, "Invalid email format"

        return True, None
```

## Creating Plugins

### Method 1: Class-Based

```python
from ia_modules.plugins.base import ConditionPlugin, PluginMetadata, PluginType

class MyCondition(ConditionPlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="my_condition",
            version="1.0.0",
            plugin_type=PluginType.CONDITION
        )

    async def evaluate(self, data: dict) -> bool:
        return data.get('value', 0) > 10
```

### Method 2: Using Decorators

```python
from ia_modules.plugins.decorators import condition_plugin
from ia_modules.plugins.base import ConditionPlugin

@condition_plugin(
    name="my_condition",
    version="1.0.0",
    description="Check if value > 10"
)
class MyCondition(ConditionPlugin):
    async def evaluate(self, data: dict) -> bool:
        return data.get('value', 0) > 10
```

### Plugin Configuration

Plugins can access configuration through `self.config`:

```python
class ConfigurableCondition(ConditionPlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="configurable_condition",
            version="1.0.0",
            plugin_type=PluginType.CONDITION,
            config_schema={
                "type": "object",
                "properties": {
                    "threshold": {"type": "number"},
                    "operator": {"type": "string", "enum": [">", "<", ">=", "<="]}
                },
                "required": ["threshold"]
            }
        )

    async def evaluate(self, data: dict) -> bool:
        value = data.get('value', 0)
        threshold = self.config.get('threshold')
        operator = self.config.get('operator', '>')

        if operator == '>':
            return value > threshold
        elif operator == '<':
            return value < threshold
        elif operator == '>=':
            return value >= threshold
        elif operator == '<=':
            return value <= threshold

        return False
```

### Plugin Lifecycle

Plugins can implement lifecycle methods:

```python
class LifecyclePlugin(ConditionPlugin):
    async def _initialize(self):
        """Called when plugin is first loaded"""
        self.logger.info("Initializing plugin")
        self.connection = await setup_connection()

    async def _shutdown(self):
        """Called when plugin is unloaded"""
        self.logger.info("Shutting down plugin")
        await self.connection.close()

    async def evaluate(self, data: dict) -> bool:
        return await self.connection.query(data)
```

## Plugin Registry

### Registering Plugins

```python
from ia_modules.plugins import get_registry

# Get global registry
registry = get_registry()

# Register a plugin class
registry.register(MyCondition)

# Register with config
registry.register(MyCondition, config={'threshold': 20})
```

### Using Registered Plugins

```python
# Get plugin instance
plugin = registry.get("my_condition")

# Use the plugin
result = await plugin.evaluate({'value': 15})

# List all plugins
all_plugins = registry.list_plugins()

# List by type
from ia_modules.plugins import PluginType
conditions = registry.list_plugins(PluginType.CONDITION)
```

### Plugin Information

```python
# Get plugin metadata
info = registry.get_info("my_condition")
print(f"Name: {info['name']}")
print(f"Version: {info['version']}")
print(f"Type: {info['type']}")
```

## Built-in Plugins

### Time Plugins

Located in `plugins/builtin/time_plugin.py`:

**business_hours**: Check if current time is within business hours

```python
config = {
    "start_hour": 9,
    "end_hour": 17,
    "weekdays_only": True
}
```

**time_range**: Check if current time is within specified range

```python
config = {
    "start_time": "09:00",
    "end_time": "17:00"
}
```

### Database Plugins

Located in `plugins/builtin/database_plugin.py`:

**database_record_exists**: Check if a database record exists

```python
config = {
    "table": "users",
    "id_field": "user_id",
    "id_key": "id"
}
```

### API Plugins

Located in `plugins/builtin/api_plugin.py`:

**api_status_condition**: Check API endpoint status

```python
config = {
    "url": "https://api.example.com/health",
    "expected_status": 200
}
```

### Validation Plugins

Located in `plugins/builtin/validation_plugin.py`:

**email_validator**: Validate email format
**range_validator**: Validate numeric range
**regex_validator**: Validate using regex pattern

## Using Plugins in Pipelines

### In Pipeline JSON

```json
{
  "name": "plugin_example",
  "steps": [
    {
      "id": "check_value",
      "module": "my_steps",
      "step_class": "CheckValueStep"
    },
    {
      "id": "process_high",
      "module": "my_steps",
      "step_class": "ProcessHighStep"
    },
    {
      "id": "process_low",
      "module": "my_steps",
      "step_class": "ProcessLowStep"
    }
  ],
  "flow": {
    "start_at": "check_value",
    "paths": [
      {
        "from": "check_value",
        "to": "process_high",
        "condition": {
          "type": "plugin",
          "plugin": "threshold_condition",
          "config": {
            "threshold": 100
          }
        }
      },
      {
        "from": "check_value",
        "to": "process_low",
        "condition": {
          "type": "default"
        }
      }
    ]
  }
}
```

### Programmatic Usage

```python
from ia_modules.plugins import get_registry

# Register plugin
registry = get_registry()
registry.register(ThresholdCondition)

# Use plugin
condition = registry.get("threshold_condition")
condition.config = {'threshold': 50}

# Evaluate
data = {'value': 75}
result = await condition.evaluate(data)
print(f"Condition passed: {result}")  # True
```

## Testing Plugins

### Unit Tests

```python
import pytest
from my_plugins import ThresholdCondition

class TestThresholdCondition:
    @pytest.mark.asyncio
    async def test_above_threshold(self):
        """Test value above threshold"""
        plugin = ThresholdCondition({'threshold': 10})
        result = await plugin.evaluate({'value': 15})
        assert result is True

    @pytest.mark.asyncio
    async def test_below_threshold(self):
        """Test value below threshold"""
        plugin = ThresholdCondition({'threshold': 10})
        result = await plugin.evaluate({'value': 5})
        assert result is False

    @pytest.mark.asyncio
    async def test_equal_to_threshold(self):
        """Test value equal to threshold"""
        plugin = ThresholdCondition({'threshold': 10})
        result = await plugin.evaluate({'value': 10})
        assert result is False  # Not greater than

    @pytest.mark.asyncio
    async def test_missing_value(self):
        """Test missing value defaults to 0"""
        plugin = ThresholdCondition({'threshold': 10})
        result = await plugin.evaluate({})
        assert result is False
```

### Integration Tests

```python
import pytest
from ia_modules.plugins import get_registry
from ia_modules.plugins.registry import reset_registry
from ia_modules.pipeline.runner import run_pipeline_from_json

@pytest.mark.asyncio
async def test_plugin_in_pipeline():
    """Test plugin integration with pipeline"""
    # Reset registry for clean test
    reset_registry()

    # Register plugin
    registry = get_registry()
    registry.register(ThresholdCondition)

    # Run pipeline that uses the plugin
    result = await run_pipeline_from_json(
        'tests/pipelines/plugin_example/pipeline.json',
        input_data={'value': 75}
    )

    # Verify plugin routing worked
    assert 'process_high' in result
```

## Examples

### Example 1: Business Hours Condition

```python
from ia_modules.plugins.base import ConditionPlugin, PluginMetadata, PluginType
from datetime import datetime

class BusinessHoursCondition(ConditionPlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="business_hours",
            version="1.0.0",
            description="Check if within business hours",
            plugin_type=PluginType.CONDITION
        )

    async def evaluate(self, data: dict) -> bool:
        now = datetime.now()

        # Get config
        start_hour = self.config.get('start_hour', 9)
        end_hour = self.config.get('end_hour', 17)
        weekdays_only = self.config.get('weekdays_only', True)

        # Check weekday
        if weekdays_only and now.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False

        # Check hours
        return start_hour <= now.hour < end_hour
```

**Usage:**
```python
from ia_modules.plugins import get_registry

registry = get_registry()
registry.register(BusinessHoursCondition, config={
    'start_hour': 9,
    'end_hour': 17,
    'weekdays_only': True
})

# In pipeline
condition = registry.get("business_hours")
is_business_hours = await condition.evaluate({})
```

### Example 2: Data Validator

```python
from ia_modules.plugins.base import ValidatorPlugin, PluginMetadata, PluginType

class UserDataValidator(ValidatorPlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="user_data_validator",
            version="1.0.0",
            description="Validate user data",
            plugin_type=PluginType.VALIDATOR
        )

    async def validate(self, data: dict) -> tuple[bool, Optional[str]]:
        # Check required fields
        required_fields = ['name', 'email', 'age']
        for field in required_fields:
            if field not in data:
                return False, f"Missing required field: {field}"

        # Validate age
        age = data.get('age')
        if not isinstance(age, int) or age < 18 or age > 120:
            return False, "Age must be between 18 and 120"

        # Validate email
        import re
        email = data.get('email')
        if not re.match(r'^[\w\.-]+@[\w\.-]+\.\w+$', email):
            return False, "Invalid email format"

        return True, None
```

**Usage:**
```python
validator = UserDataValidator()

# Valid data
is_valid, error = await validator.validate({
    'name': 'John Doe',
    'email': 'john@example.com',
    'age': 25
})
# is_valid = True, error = None

# Invalid data
is_valid, error = await validator.validate({
    'name': 'Jane Doe',
    'email': 'invalid-email',
    'age': 25
})
# is_valid = False, error = "Invalid email format"
```

### Example 3: Transform Plugin

```python
from ia_modules.plugins.base import TransformPlugin, PluginMetadata, PluginType

class DataEnricherTransform(TransformPlugin):
    @property
    def metadata(self) -> PluginMetadata:
        return PluginMetadata(
            name="data_enricher",
            version="1.0.0",
            description="Enrich data with additional fields",
            plugin_type=PluginType.TRANSFORM
        )

    async def transform(self, data: dict) -> dict:
        """Add metadata and computed fields"""
        from datetime import datetime

        enriched = data.copy()

        # Add timestamp
        enriched['processed_at'] = datetime.now().isoformat()

        # Add computed fields
        if 'price' in data and 'quantity' in data:
            enriched['total'] = data['price'] * data['quantity']

        # Add metadata
        enriched['metadata'] = {
            'transformer': self.metadata.name,
            'version': self.metadata.version
        }

        return enriched
```

## Best Practices

### 1. Descriptive Names

Use clear, descriptive plugin names that indicate purpose:

```python
# Good
name="email_validator"
name="business_hours_condition"
name="user_data_enricher"

# Bad
name="check"
name="plugin1"
name="my_plugin"
```

### 2. Error Handling

Always handle errors gracefully:

```python
async def evaluate(self, data: dict) -> bool:
    try:
        value = data.get('value', 0)
        return value > self.config['threshold']
    except Exception as e:
        self.logger.error(f"Evaluation failed: {e}")
        return False  # Safe default
```

### 3. Configuration Validation

Validate configuration on initialization:

```python
def __init__(self, config=None):
    super().__init__(config)

    # Validate required config
    if 'threshold' not in self.config:
        raise ValueError("threshold is required in config")

    if not isinstance(self.config['threshold'], (int, float)):
        raise ValueError("threshold must be a number")
```

### 4. Logging

Use the built-in logger:

```python
async def evaluate(self, data: dict) -> bool:
    self.logger.debug(f"Evaluating condition with data: {data}")

    result = data.get('value', 0) > 10

    self.logger.info(f"Condition result: {result}")
    return result
```

### 5. Type Hints

Use type hints for clarity:

```python
from typing import Dict, Any, Optional, Tuple

async def evaluate(self, data: Dict[str, Any]) -> bool:
    ...

async def validate(self, data: Dict[str, Any]) -> Tuple[bool, Optional[str]]:
    ...
```

## Documentation

- [Developer Guide](DEVELOPER_GUIDE.md) - API reference
- [Getting Started](GETTING_STARTED.md) - Quick start
- [Testing Guide](TESTING_GUIDE.md) - Testing patterns
- [Pipeline Architecture](PIPELINE_ARCHITECTURE.md) - Pipeline design
