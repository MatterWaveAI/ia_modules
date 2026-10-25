"""
Plugin Base Classes

Core abstractions for the plugin system.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional, List
from dataclasses import dataclass, field
from enum import Enum
import logging


class PluginType(Enum):
    """Types of plugins supported"""
    CONDITION = "condition"  # Custom condition functions
    STEP = "step"  # Custom pipeline steps
    TRANSFORM = "transform"  # Data transformers
    VALIDATOR = "validator"  # Custom validators
    HOOK = "hook"  # Lifecycle hooks
    REPORTER = "reporter"  # Custom reporters


@dataclass
class PluginMetadata:
    """Metadata for a plugin"""
    name: str
    version: str
    author: Optional[str] = None
    description: Optional[str] = None
    plugin_type: PluginType = PluginType.CONDITION
    tags: List[str] = field(default_factory=list)
    dependencies: List[str] = field(default_factory=list)
    config_schema: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if not self.name:
            raise ValueError("Plugin name is required")
        if not self.version:
            raise ValueError("Plugin version is required")


class Plugin(ABC):
    """
    Base class for all plugins

    Plugins extend pipeline functionality with custom behavior.
    All plugins must implement this interface.
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or {}
        self.logger = logging.getLogger(f"Plugin.{self.__class__.__name__}")
        self._initialized: bool = True

    @property
    @abstractmethod
    def metadata(self) -> PluginMetadata:
        """Return plugin metadata"""
        pass

    async def shutdown(self) -> None:
        """
        Cleanup plugin resources

        Called when plugin is unloaded or system shuts down.
        Override to add custom cleanup logic.
        """
        self.logger.debug(f"Shutting down plugin: {self.metadata.name}")
        await self._shutdown()

    async def _shutdown(self) -> None:
        """Override for custom shutdown logic"""
        pass

    def validate_config(self) -> bool:
        """
        Validate plugin configuration

        Override to add custom validation logic.

        Returns:
            True if config is valid, False otherwise
        """
        if self.metadata.config_schema:
            # Could integrate with jsonschema here
            pass
        return True

    def get_info(self) -> Dict[str, Any]:
        """Get plugin information"""
        return {
            'name': self.metadata.name,
            'version': self.metadata.version,
            'author': self.metadata.author,
            'description': self.metadata.description,
            'type': self.metadata.plugin_type.value,
            'tags': self.metadata.tags,
            'dependencies': self.metadata.dependencies,
            'initialized': self._initialized
        }


class ConditionPlugin(Plugin):
    """
    Base class for condition plugins

    Condition plugins provide custom logic for conditional routing
    in pipeline flows.
    """

    @property
    def metadata(self) -> PluginMetadata:
        """Default metadata for condition plugins"""
        return PluginMetadata(
            name=self.__class__.__name__,
            version="1.0.0",
            plugin_type=PluginType.CONDITION
        )

    @abstractmethod
    async def evaluate(self, data: Dict[str, Any]) -> bool:
        """
        Evaluate the condition

        Args:
            data: Pipeline data to evaluate

        Returns:
            True if condition is met, False otherwise
        """
        pass

    def __call__(self, data: Dict[str, Any]) -> bool:
        """Allow plugin to be called directly"""
        import asyncio
        return asyncio.run(self.evaluate(data))


class StepPlugin(Plugin):
    """
    Base class for step plugins

    Step plugins provide custom processing steps that can be
    used in pipelines.
    """

    @property
    def metadata(self) -> PluginMetadata:
        """Default metadata for step plugins"""
        return PluginMetadata(
            name=self.__class__.__name__,
            version="1.0.0",
            plugin_type=PluginType.STEP
        )

    @abstractmethod
    async def execute(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute the step

        Args:
            data: Input data

        Returns:
            Processed output data
        """
        pass


class TransformPlugin(Plugin):
    """
    Base class for transform plugins

    Transform plugins modify data flowing through the pipeline.
    """

    @property
    def metadata(self) -> PluginMetadata:
        """Default metadata for transform plugins"""
        return PluginMetadata(
            name=self.__class__.__name__,
            version="1.0.0",
            plugin_type=PluginType.TRANSFORM
        )

    @abstractmethod
    async def transform(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Transform data

        Args:
            data: Input data

        Returns:
            Transformed data
        """
        pass


class ValidatorPlugin(Plugin):
    """
    Base class for validator plugins

    Validator plugins provide custom validation logic for
    pipeline data or configuration.
    """

    @property
    def metadata(self) -> PluginMetadata:
        """Default metadata for validator plugins"""
        return PluginMetadata(
            name=self.__class__.__name__,
            version="1.0.0",
            plugin_type=PluginType.VALIDATOR
        )

    @abstractmethod
    async def validate(self, data: Dict[str, Any]) -> tuple[bool, Optional[str]]:
        """
        Validate data

        Args:
            data: Data to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        pass


class HookPlugin(Plugin):
    """
    Base class for hook plugins

    Hook plugins respond to lifecycle events in the pipeline.
    """

    @property
    def metadata(self) -> PluginMetadata:
        """Default metadata for hook plugins"""
        return PluginMetadata(
            name=self.__class__.__name__,
            version="1.0.0",
            plugin_type=PluginType.HOOK
        )

    async def on_pipeline_start(self, pipeline_name: str, data: Dict[str, Any]) -> None:
        """Called when pipeline starts"""
        pass

    async def on_pipeline_end(self, pipeline_name: str, result: Dict[str, Any]) -> None:
        """Called when pipeline ends"""
        pass

    async def on_step_start(self, step_name: str, data: Dict[str, Any]) -> None:
        """Called before step executes"""
        pass

    async def on_step_end(self, step_name: str, result: Dict[str, Any]) -> None:
        """Called after step executes"""
        pass

    async def on_error(self, error: Exception, context: Dict[str, Any]) -> None:
        """Called when error occurs"""
        pass
