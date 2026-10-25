"""
Plugin Decorators

Convenient decorators for creating plugins.
"""

from typing import Type, Optional, Dict, Any, Callable

from .base import (
    Plugin,
    ConditionPlugin,
    StepPlugin,
    PluginMetadata,
    PluginType
)
from .registry import get_registry


def plugin(
    name: str,
    version: str = "1.0.0",
    author: Optional[str] = None,
    description: Optional[str] = None,
    plugin_type: PluginType = PluginType.CONDITION,
    tags: Optional[list[str]] = None,
    dependencies: Optional[list[str]] = None,
    auto_register: bool = True
):
    """
    Decorator to create a plugin from a class

    Args:
        name: Plugin name
        version: Plugin version
        author: Plugin author
        description: Plugin description
        plugin_type: Type of plugin
        tags: Plugin tags
        dependencies: Plugin dependencies
        auto_register: Automatically register with global registry

    Example:
        @plugin(
            name="weather_condition",
            description="Check if weather meets criteria",
            tags=["weather", "condition"]
        )
        class WeatherCondition(ConditionPlugin):
            async def evaluate(self, data):
                return data.get('temperature', 0) > 20
    """
    def decorator(cls: Type[Plugin]) -> Type[Plugin]:
        # Create metadata property
        metadata = PluginMetadata(
            name=name,
            version=version,
            author=author,
            description=description,
            plugin_type=plugin_type,
            tags=tags or [],
            dependencies=dependencies or []
        )

        # Override metadata property
        cls.metadata = property(lambda self: metadata)  # type: ignore[assignment]

        # Auto-register if requested
        if auto_register:
            try:
                registry = get_registry()
                registry.register(cls)
            except Exception as e:
                import logging
                logging.warning(f"Failed to auto-register plugin '{name}': {e}")

        return cls

    return decorator


def condition_plugin(
    name: str,
    version: str = "1.0.0",
    author: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[list[str]] = None,
    auto_register: bool = True
):
    """
    Decorator to create a condition plugin

    Example:
        @condition_plugin(
            name="threshold_check",
            description="Check if value exceeds threshold"
        )
        class ThresholdCheck(ConditionPlugin):
            async def evaluate(self, data):
                threshold = self.config.get('threshold', 0)
                value = data.get('value', 0)
                return value > threshold
    """
    return plugin(
        name=name,
        version=version,
        author=author,
        description=description,
        plugin_type=PluginType.CONDITION,
        tags=tags,
        auto_register=auto_register
    )


def step_plugin(
    name: str,
    version: str = "1.0.0",
    author: Optional[str] = None,
    description: Optional[str] = None,
    tags: Optional[list[str]] = None,
    auto_register: bool = True
):
    """
    Decorator to create a step plugin

    Example:
        @step_plugin(
            name="data_enrichment",
            description="Enrich data with external API"
        )
        class DataEnrichment(StepPlugin):
            async def execute(self, data):
                # Enrich data
                data['enriched'] = True
                return data
    """
    return plugin(
        name=name,
        version=version,
        author=author,
        description=description,
        plugin_type=PluginType.STEP,
        tags=tags,
        auto_register=auto_register
    )


def function_plugin(
    name: str,
    version: str = "1.0.0",
    plugin_type: PluginType = PluginType.CONDITION,
    description: Optional[str] = None
):
    """
    Decorator to create a plugin from a simple function

    Example:
        @function_plugin(name="is_positive", description="Check if number is positive")
        async def is_positive(data: dict) -> bool:
            return data.get('value', 0) > 0

    Args:
        name: Plugin name
        version: Plugin version
        plugin_type: Type of plugin
        description: Plugin description
    """
    def decorator(func: Callable) -> Type[Plugin]:
        # Create appropriate base class
        if plugin_type == PluginType.CONDITION:
            class FunctionConditionPlugin(ConditionPlugin):
                async def evaluate(self, data: Dict[str, Any]) -> bool:
                    return await func(data)

            plugin_class = FunctionConditionPlugin

        elif plugin_type == PluginType.STEP:
            class FunctionStepPlugin(StepPlugin):
                async def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
                    return await func(data)

            plugin_class = FunctionStepPlugin

        else:
            raise ValueError(f"Unsupported plugin type for function plugin: {plugin_type}")

        # Set metadata
        metadata = PluginMetadata(
            name=name,
            version=version,
            description=description or func.__doc__,
            plugin_type=plugin_type
        )

        plugin_class.metadata = property(lambda self: metadata)  # type: ignore[assignment]
        plugin_class.__name__ = name
        plugin_class.__doc__ = description or func.__doc__

        # Register
        try:
            registry = get_registry()
            registry.register(plugin_class)
        except Exception as e:
            import logging
            logging.warning(f"Failed to auto-register function plugin '{name}': {e}")

        return plugin_class

    return decorator
