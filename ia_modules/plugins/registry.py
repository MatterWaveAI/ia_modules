"""
Plugin Registry

Central registry for managing plugins.
"""

from typing import Any, Dict, List, Optional, Type
import logging
from .base import Plugin, PluginType


class PluginRegistry:
    """
    Central registry for plugins

    Features:
    - Register plugins by name and type
    - Discover plugins
    - Manage plugin lifecycle
    - Resolve dependencies
    """

    _instance: Optional['PluginRegistry'] = None

    def __init__(self):
        self._plugins: Dict[str, Plugin] = {}
        self._plugin_classes: Dict[str, Type[Plugin]] = {}
        self._plugins_by_type: Dict[PluginType, List[str]] = {
            plugin_type: [] for plugin_type in PluginType
        }
        self.logger = logging.getLogger("PluginRegistry")

    @classmethod
    def get_instance(cls) -> 'PluginRegistry':
        """Get singleton registry instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(
        self,
        plugin_class: Type[Plugin],
        config: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Register a plugin class

        Args:
            plugin_class: Plugin class to register
            config: Optional configuration for plugin instance
        """
        # Create instance to get metadata
        instance = plugin_class(config)
        metadata = instance.metadata

        if metadata.name in self._plugins:
            self.logger.warning(f"Plugin '{metadata.name}' already registered, overwriting")

        # Store both class and instance
        self._plugin_classes[metadata.name] = plugin_class
        self._plugins[metadata.name] = instance

        # Index by type
        if metadata.name not in self._plugins_by_type[metadata.plugin_type]:
            self._plugins_by_type[metadata.plugin_type].append(metadata.name)

        self.logger.info(f"Registered plugin: {metadata.name} v{metadata.version}")

    def unregister(self, plugin_name: str) -> None:
        """
        Unregister a plugin

        Args:
            plugin_name: Name of plugin to unregister
        """
        if plugin_name not in self._plugins:
            self.logger.warning(f"Plugin '{plugin_name}' not found")
            return

        plugin = self._plugins[plugin_name]
        plugin_type = plugin.metadata.plugin_type

        # Remove from type index
        if plugin_name in self._plugins_by_type[plugin_type]:
            self._plugins_by_type[plugin_type].remove(plugin_name)

        # Remove from main registry
        del self._plugins[plugin_name]
        del self._plugin_classes[plugin_name]

        self.logger.info(f"Unregistered plugin: {plugin_name}")

    def get(self, plugin_name: str) -> Optional[Plugin]:
        """
        Get a plugin instance by name

        Args:
            plugin_name: Name of plugin

        Returns:
            Plugin instance or None if not found
        """
        return self._plugins.get(plugin_name)

    def get_class(self, plugin_name: str) -> Optional[Type[Plugin]]:
        """
        Get a plugin class by name

        Args:
            plugin_name: Name of plugin

        Returns:
            Plugin class or None if not found
        """
        return self._plugin_classes.get(plugin_name)

    def create_instance(
        self,
        plugin_name: str,
        config: Optional[Dict[str, Any]] = None
    ) -> Optional[Plugin]:
        """
        Create a new instance of a plugin

        Args:
            plugin_name: Name of plugin
            config: Configuration for instance

        Returns:
            New plugin instance or None if not found
        """
        plugin_class = self.get_class(plugin_name)
        if plugin_class is None:
            return None

        return plugin_class(config)

    def list_plugins(
        self,
        plugin_type: Optional[PluginType] = None
    ) -> List[str]:
        """
        List registered plugins

        Args:
            plugin_type: Optional filter by type

        Returns:
            List of plugin names
        """
        if plugin_type:
            return self._plugins_by_type[plugin_type].copy()
        return list(self._plugins.keys())

    def get_by_type(self, plugin_type: PluginType) -> List[Plugin]:
        """
        Get all plugins of a specific type

        Args:
            plugin_type: Type of plugins to retrieve

        Returns:
            List of plugin instances
        """
        plugin_names = self._plugins_by_type[plugin_type]
        return [self._plugins[name] for name in plugin_names]

    def get_info(self, plugin_name: str) -> Optional[Dict[str, Any]]:
        """
        Get information about a plugin

        Args:
            plugin_name: Name of plugin

        Returns:
            Plugin info dict or None if not found
        """
        plugin = self.get(plugin_name)
        if plugin is None:
            return None

        return plugin.get_info()

    def get_all_info(self) -> List[Dict[str, Any]]:
        """
        Get information about all registered plugins

        Returns:
            List of plugin info dicts
        """
        return [plugin.get_info() for plugin in self._plugins.values()]

    async def shutdown_all(self) -> None:
        """Shutdown all registered plugins"""
        self.logger.info("Shutting down all plugins")

        for plugin_name, plugin in self._plugins.items():
            try:
                await plugin.shutdown()
            except Exception as e:
                self.logger.error(f"Failed to shutdown plugin '{plugin_name}': {e}")

    def clear(self) -> None:
        """Clear all registered plugins"""
        self._plugins.clear()
        self._plugin_classes.clear()
        for plugin_type in PluginType:
            self._plugins_by_type[plugin_type].clear()
        self.logger.info("Cleared all plugins")

    def check_dependencies(self, plugin_name: str) -> tuple[bool, List[str]]:
        """
        Check if plugin dependencies are satisfied

        Args:
            plugin_name: Name of plugin to check

        Returns:
            Tuple of (all_satisfied, missing_dependencies)
        """
        plugin = self.get(plugin_name)
        if plugin is None:
            return False, [plugin_name]

        missing = []
        for dep in plugin.metadata.dependencies:
            if dep not in self._plugins:
                missing.append(dep)

        return len(missing) == 0, missing

    def get_dependency_order(self) -> List[str]:
        """
        Get plugins in dependency order

        Returns:
            List of plugin names sorted by dependencies

        Raises:
            ValueError: If circular dependencies detected
        """
        # Simple topological sort
        result = []
        visited = set()
        temp_visited = set()

        def visit(name: str):
            if name in temp_visited:
                raise ValueError(f"Circular dependency detected involving '{name}'")
            if name in visited:
                return

            temp_visited.add(name)

            plugin = self.get(name)
            if plugin:
                for dep in plugin.metadata.dependencies:
                    if dep in self._plugins:
                        visit(dep)

            temp_visited.remove(name)
            visited.add(name)
            result.append(name)

        for plugin_name in self._plugins.keys():
            if plugin_name not in visited:
                visit(plugin_name)

        return result


# Global registry instance
_global_registry: Optional[PluginRegistry] = None


def get_registry() -> PluginRegistry:
    """
    Get the global plugin registry instance

    Returns:
        Global PluginRegistry instance
    """
    global _global_registry
    if _global_registry is None:
        _global_registry = PluginRegistry.get_instance()
    return _global_registry


def reset_registry() -> None:
    """Reset the global registry (useful for testing)"""
    global _global_registry
    if _global_registry:
        _global_registry.clear()
    _global_registry = None
