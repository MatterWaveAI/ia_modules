"""
Plugin System for IA Modules

Extensible plugin architecture for custom conditions, steps, and behaviors.
"""

from .base import Plugin, PluginMetadata, PluginType
from .registry import PluginRegistry, get_registry
from .loader import PluginLoader
from .decorators import plugin, condition_plugin, step_plugin

__all__ = [
    # Base classes
    'Plugin',
    'PluginMetadata',
    'PluginType',

    # Registry
    'PluginRegistry',
    'get_registry',

    # Loading
    'PluginLoader',

    # Decorators
    'plugin',
    'condition_plugin',
    'step_plugin',
]
