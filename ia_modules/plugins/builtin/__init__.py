"""
Built-in Plugins

Collection of useful plugins that ship with IA Modules.
"""

# Import all builtin plugins so they auto-register
from . import weather_plugin
from . import database_plugin
from . import api_plugin
from . import time_plugin
from . import validation_plugin

__all__ = [
    'weather_plugin',
    'database_plugin',
    'api_plugin',
    'time_plugin',
    'validation_plugin',
]
