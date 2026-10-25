"""
Plugin Loader

Discovers and loads plugins from directories.
"""

import importlib
import importlib.util
import sys
from pathlib import Path
from typing import List, Optional, Dict, Any
import logging
import inspect

from .base import Plugin
from .registry import PluginRegistry, get_registry


class PluginLoader:
    """
    Discovers and loads plugins

    Features:
    - Load plugins from directories
    - Load plugins from modules
    - Auto-discover plugin classes
    - Handle plugin dependencies
    """

    def __init__(self, registry: Optional[PluginRegistry] = None):
        self.registry = registry or get_registry()
        self.logger = logging.getLogger("PluginLoader")

    def load_from_directory(
        self,
        directory: Path,
        pattern: str = "*.py",
        recursive: bool = True
    ) -> int:
        """
        Load all plugins from a directory

        Args:
            directory: Directory to search
            pattern: File pattern to match (default: *.py)
            recursive: Search subdirectories (default: True)

        Returns:
            Number of plugins loaded
        """
        if not directory.exists():
            self.logger.warning(f"Directory not found: {directory}")
            return 0

        if not directory.is_dir():
            self.logger.warning(f"Not a directory: {directory}")
            return 0

        self.logger.info(f"Loading plugins from: {directory}")

        loaded_count = 0

        # Find all Python files
        if recursive:
            files = directory.rglob(pattern)
        else:
            files = directory.glob(pattern)

        for filepath in files:
            # Skip __init__.py and private files
            if filepath.name.startswith('_'):
                continue

            try:
                count = self.load_from_file(filepath)
                loaded_count += count
            except Exception as e:
                self.logger.error(f"Failed to load plugins from {filepath}: {e}")

        self.logger.info(f"Loaded {loaded_count} plugins from {directory}")
        return loaded_count

    def load_from_file(self, filepath: Path) -> int:
        """
        Load plugins from a Python file

        Args:
            filepath: Path to Python file

        Returns:
            Number of plugins loaded
        """
        if not filepath.exists():
            self.logger.warning(f"File not found: {filepath}")
            return 0

        # Generate module name from file path
        module_name = filepath.stem

        # Load module
        spec = importlib.util.spec_from_file_location(module_name, filepath)
        if spec is None or spec.loader is None:
            self.logger.warning(f"Could not load module from: {filepath}")
            return 0

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module

        try:
            spec.loader.exec_module(module)
        except Exception as e:
            self.logger.error(f"Error loading module {module_name}: {e}")
            return 0

        # Discover plugin classes in module
        return self.discover_plugins_in_module(module)

    def load_from_module(self, module_name: str) -> int:
        """
        Load plugins from a Python module

        Args:
            module_name: Fully qualified module name

        Returns:
            Number of plugins loaded
        """
        try:
            module = importlib.import_module(module_name)
            return self.discover_plugins_in_module(module)
        except ImportError as e:
            self.logger.error(f"Failed to import module '{module_name}': {e}")
            return 0

    def discover_plugins_in_module(self, module) -> int:
        """
        Discover and register plugin classes in a module

        Args:
            module: Python module object

        Returns:
            Number of plugins discovered
        """
        loaded_count = 0

        # Inspect module for Plugin subclasses
        for name, obj in inspect.getmembers(module):
            if self._is_plugin_class(obj):
                try:
                    self.registry.register(obj)
                    loaded_count += 1
                except Exception as e:
                    self.logger.error(f"Failed to register plugin '{name}': {e}")

        return loaded_count

    def _is_plugin_class(self, obj) -> bool:
        """Check if object is a valid plugin class"""
        return (
            inspect.isclass(obj) and
            issubclass(obj, Plugin) and
            obj is not Plugin and
            not inspect.isabstract(obj)
        )

    def load_plugin_package(
        self,
        package_path: Path,
        config: Optional[Dict[str, Any]] = None
    ) -> bool:
        """
        Load a plugin package (directory with __init__.py)

        Args:
            package_path: Path to plugin package
            config: Optional configuration for plugins

        Returns:
            True if loaded successfully
        """
        if not package_path.is_dir():
            self.logger.warning(f"Not a directory: {package_path}")
            return False

        init_file = package_path / "__init__.py"
        if not init_file.exists():
            self.logger.warning(f"No __init__.py in {package_path}")
            return False

        # Add parent to sys.path temporarily
        parent_path = str(package_path.parent)
        if parent_path not in sys.path:
            sys.path.insert(0, parent_path)

        try:
            # Import package
            package_name = package_path.name
            module = importlib.import_module(package_name)

            # Look for plugin classes
            count = self.discover_plugins_in_module(module)

            if count > 0:
                self.logger.info(f"Loaded {count} plugins from package: {package_name}")
                return True
            else:
                self.logger.warning(f"No plugins found in package: {package_name}")
                return False

        except Exception as e:
            self.logger.error(f"Failed to load plugin package {package_path}: {e}")
            return False
        finally:
            # Remove from sys.path
            if parent_path in sys.path:
                sys.path.remove(parent_path)

    def scan_plugin_directories(self, base_dirs: List[Path]) -> int:
        """
        Scan multiple directories for plugins

        Args:
            base_dirs: List of directories to scan

        Returns:
            Total number of plugins loaded
        """
        total_loaded = 0

        for directory in base_dirs:
            if not directory.exists():
                self.logger.debug(f"Skipping non-existent directory: {directory}")
                continue

            count = self.load_from_directory(directory)
            total_loaded += count

        return total_loaded

    def get_default_plugin_dirs(self) -> List[Path]:
        """
        Get default plugin directories to search

        Returns:
            List of default plugin directories
        """
        dirs = []

        # 1. Built-in plugins
        builtin_dir = Path(__file__).parent / "builtin"
        if builtin_dir.exists():
            dirs.append(builtin_dir)

        # 2. User plugins (~/.ia_modules/plugins)
        user_dir = Path.home() / ".ia_modules" / "plugins"
        if user_dir.exists():
            dirs.append(user_dir)

        # 3. Current directory plugins
        current_dir = Path.cwd() / "plugins"
        if current_dir.exists():
            dirs.append(current_dir)

        # 4. Environment variable
        import os
        env_paths = os.environ.get('IA_PLUGIN_PATH', '')
        if env_paths:
            for path_str in env_paths.split(':'):
                path = Path(path_str)
                if path.exists():
                    dirs.append(path)

        return dirs

    def auto_discover(self) -> int:
        """
        Automatically discover and load plugins from default locations

        Returns:
            Number of plugins loaded
        """
        self.logger.info("Auto-discovering plugins")
        plugin_dirs = self.get_default_plugin_dirs()
        return self.scan_plugin_directories(plugin_dirs)


def auto_load_plugins(registry: Optional[PluginRegistry] = None) -> int:
    """
    Convenience function to auto-load plugins

    Args:
        registry: Optional registry to use

    Returns:
        Number of plugins loaded
    """
    loader = PluginLoader(registry)
    return loader.auto_discover()
