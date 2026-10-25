"""Plugin Service - Manages plugin registry for the showcase app"""

import logging
from typing import Dict, Any, List, Optional
from pathlib import Path

from ia_modules.plugins.registry import PluginRegistry
from ia_modules.plugins.loader import PluginLoader
from ia_modules.plugins.base import Plugin, PluginType

logger = logging.getLogger(__name__)


class PluginService:
    """Service for managing plugins through the ia_modules plugin system"""

    def __init__(self):
        self.registry = PluginRegistry()
        self.loader = PluginLoader(self.registry)
        self._load_builtin_plugins()

    def _load_builtin_plugins(self):
        """Load all builtin plugins on initialization"""
        builtin_modules = [
            "ia_modules.plugins.builtin.time_plugin",
            "ia_modules.plugins.builtin.api_plugin",
            "ia_modules.plugins.builtin.database_plugin",
            "ia_modules.plugins.builtin.validation_plugin",
            "ia_modules.plugins.builtin.weather_plugin",
        ]
        count = 0
        for module_name in builtin_modules:
            count += self.loader.load_from_module(module_name)
        logger.info(f"Loaded {count} builtin plugins")

    def list_plugins(self) -> List[Dict[str, Any]]:
        """List all registered plugins with metadata"""
        plugins = []
        for name in self.registry.list_plugins():
            plugin = self.registry.get(name)
            if plugin:
                plugins.append(self._plugin_to_dict(plugin))
        return plugins

    def get_plugin(self, name: str) -> Optional[Dict[str, Any]]:
        """Get detailed info about a specific plugin"""
        plugin = self.registry.get(name)
        if plugin is None:
            return None
        info = self._plugin_to_dict(plugin)
        # Add config schema if available
        info["config_schema"] = plugin.metadata.config_schema
        info["dependencies"] = plugin.metadata.dependencies
        # Check dependency status
        satisfied, missing = self.registry.check_dependencies(name)
        info["dependencies_satisfied"] = satisfied
        info["missing_dependencies"] = missing
        return info

    async def execute_plugin(self, name: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a plugin with given parameters"""
        plugin = self.registry.get(name)
        if plugin is None:
            raise ValueError(f"Plugin '{name}' not found")

        metadata = plugin.metadata
        plugin_type = metadata.plugin_type

        try:
            if plugin_type == PluginType.CONDITION:
                result = await plugin.evaluate(params)
                return {"result": result, "type": "condition", "plugin": name}
            elif plugin_type == PluginType.STEP:
                result = await plugin.execute(params)
                return {"result": result, "type": "step", "plugin": name}
            elif plugin_type == PluginType.VALIDATOR:
                is_valid, error_msg = await plugin.validate(params)
                return {"result": is_valid, "error": error_msg, "type": "validator", "plugin": name}
            elif plugin_type == PluginType.TRANSFORM:
                result = await plugin.transform(params)
                return {"result": result, "type": "transform", "plugin": name}
            else:
                raise ValueError(f"Plugin type '{plugin_type.value}' does not support direct execution")
        except Exception as e:
            logger.error(f"Plugin execution failed for '{name}': {e}")
            raise

    def load_plugin(self, path: str) -> Dict[str, Any]:
        """Load a plugin from a file path"""
        filepath = Path(path)
        if not filepath.exists():
            raise FileNotFoundError(f"Plugin file not found: {path}")

        count = self.loader.load_from_file(filepath)
        return {"loaded_count": count, "path": str(filepath)}

    def unload_plugin(self, name: str) -> bool:
        """Unload a plugin by name"""
        plugin = self.registry.get(name)
        if plugin is None:
            return False
        self.registry.unregister(name)
        return True

    def _plugin_to_dict(self, plugin: Plugin) -> Dict[str, Any]:
        """Convert a plugin instance to a serializable dict"""
        metadata = plugin.metadata
        return {
            "name": metadata.name,
            "version": metadata.version,
            "author": metadata.author,
            "description": metadata.description,
            "type": metadata.plugin_type.value,
            "tags": metadata.tags,
            "status": "loaded",
        }
