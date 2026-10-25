"""Database-backed step loader for executing steps from database storage

This module provides a DatabaseStepLoader that loads step classes from database
storage instead of the filesystem, enabling web-based editing and execution.

Security Features:
- AST validation to prevent malicious code
- Import restrictions (only safe modules allowed)
- No eval/exec in loaded code
- Source code validation before execution

Example:
    from ia_modules.pipeline.db_step_loader import DatabaseStepLoader
    from nexusql import DatabaseManager

    db = DatabaseManager("sqlite:///pipelines.db")
    loader = DatabaseStepLoader(db)

    step_class = await loader.load_step_class(
        module_path="tests.pipelines.simple_pipeline.steps.step1",
        class_name="Step1",
        pipeline_id="abc-123"
    )
"""

import ast
import logging
from typing import Dict, Optional, Type
from nexusql import DatabaseInterface
from ia_modules.pipeline.core import Step

logger = logging.getLogger(__name__)

# Global cache for loaded step classes
_step_class_cache: Dict[str, Type[Step]] = {}


class DatabaseStepLoader:
    """Loads and executes step classes from database storage with fallback to filesystem"""

    def __init__(self, db_provider: DatabaseInterface, enable_cache: bool = True):
        """Initialize the database step loader

        Args:
            db_provider: Database interface for querying step modules
            enable_cache: Whether to cache loaded step classes (default: True)
        """
        self.db_provider = db_provider
        self.enable_cache = enable_cache

    async def load_step_class(
        self,
        module_path: str,
        class_name: str,
        pipeline_id: Optional[str] = None
    ) -> Type[Step]:
        """Load a step class from database or fallback to filesystem

        Args:
            module_path: Python module path (e.g., "tests.pipelines.simple_pipeline.steps.step1")
            class_name: Name of the step class (e.g., "Step1")
            pipeline_id: Optional pipeline ID to load pipeline-specific version

        Returns:
            Step class ready to be instantiated

        Raises:
            ImportError: If module cannot be loaded from database or filesystem
            AttributeError: If class is not found in module
        """
        # Try database first
        step_class = await self._load_from_database(module_path, class_name, pipeline_id)

        if step_class:
            return step_class

        # Fallback to filesystem (for backward compatibility)
        logger.info(f"Step {module_path}.{class_name} not found in database, using filesystem")
        return self._load_from_filesystem(module_path, class_name)

    async def _load_from_database(
        self,
        module_path: str,
        class_name: str,
        pipeline_id: Optional[str] = None
    ) -> Optional[Type[Step]]:
        """Load step class from database

        Args:
            module_path: Python module path
            class_name: Name of the step class
            pipeline_id: Optional pipeline ID for pipeline-specific version

        Returns:
            Step class or None if not found in database
        """
        # Check cache first
        cache_key = f"{module_path}.{class_name}"
        if pipeline_id:
            cache_key = f"{pipeline_id}:{cache_key}"

        if self.enable_cache and cache_key in _step_class_cache:
            logger.debug(f"Loading {cache_key} from cache")
            return _step_class_cache[cache_key]

        # Query database
        query = """
        SELECT source_code, content_hash
        FROM pipeline_step_modules
        WHERE module_path = :module_path
          AND class_name = :class_name
          AND is_active = TRUE
        """

        params = {
            'module_path': module_path,
            'class_name': class_name
        }

        # Add pipeline_id filter if provided
        if pipeline_id:
            query += " AND pipeline_id = :pipeline_id"
            params['pipeline_id'] = pipeline_id

        query += " ORDER BY updated_at DESC LIMIT 1"

        result = self.db_provider.fetch_one(query, params)

        # Handle both list and dict responses
        if not result:
            logger.debug(f"Step {module_path}.{class_name} not found in database")
            return None

        data = None
        if isinstance(result, dict):
            data = result
        elif hasattr(result, 'data') and result.data:
            data = result.data[0] if isinstance(result.data, list) else result.data

        if not data:
            logger.debug(f"Step {module_path}.{class_name} not found in database")
            return None

        source_code = data['source_code']
        content_hash = data['content_hash']

        # Compile and extract class
        step_class = self._compile_and_extract_class(source_code, class_name, module_path)

        # Cache the class
        if self.enable_cache:
            _step_class_cache[cache_key] = step_class

        logger.info(f"Loaded step class {module_path}.{class_name} from database (hash: {content_hash[:8]})")
        return step_class

    def _compile_and_extract_class(
        self,
        source_code: str,
        class_name: str,
        module_path: str
    ) -> Type[Step]:
        """Compile source code and extract the step class

        Args:
            source_code: Python source code
            class_name: Name of class to extract
            module_path: Module path for error messages

        Returns:
            Compiled step class

        Raises:
            ValueError: If source code is invalid or unsafe
            ImportError: If execution fails
            AttributeError: If class not found
            TypeError: If class is not a Step subclass
        """
        # Validate source code (basic safety check)
        self._validate_source_code(source_code)

        # Create a namespace for execution
        namespace = {
            '__name__': module_path,
            '__file__': f'<database:{module_path}>',
        }

        # Import common dependencies that steps typically need
        exec('from typing import Dict, Any, Optional, List, Union', namespace)
        exec('from ia_modules.pipeline.core import Step', namespace)

        # Execute the source code
        try:
            exec(source_code, namespace)
        except Exception as e:
            raise ImportError(f"Failed to execute step code for {module_path}.{class_name}: {e}")

        # Extract the class
        if class_name not in namespace:
            raise AttributeError(f"Class {class_name} not found in module {module_path}")

        step_class = namespace[class_name]

        # Validate it's a Step subclass
        if not issubclass(step_class, Step):
            raise TypeError(f"{class_name} is not a subclass of Step")

        return step_class

    def _validate_source_code(self, source_code: str):
        """Basic validation of source code for safety

        This performs AST-based validation to detect potentially dangerous
        operations before executing the code.

        Args:
            source_code: Python source code to validate

        Raises:
            ValueError: If code contains dangerous operations or invalid syntax
        """
        # Parse as AST to ensure it's valid Python
        try:
            tree = ast.parse(source_code)
        except SyntaxError as e:
            raise ValueError(f"Invalid Python syntax: {e}")

        # Walk the AST to check for dangerous operations
        for node in ast.walk(tree):
            # Check imports
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if not self._is_safe_import(alias.name):
                        raise ValueError(f"Potentially unsafe import: {alias.name}")

            if isinstance(node, ast.ImportFrom):
                if node.module and not self._is_safe_import(node.module):
                    raise ValueError(f"Potentially unsafe import: {node.module}")

            # Disallow exec/eval/__import__
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name):
                    if node.func.id in ('exec', 'eval', '__import__', 'compile'):
                        raise ValueError(f"Dangerous function call: {node.func.id}")

                # Also check for attribute calls like os.system
                if isinstance(node.func, ast.Attribute):
                    if node.func.attr in ('system', 'popen', 'spawn'):
                        raise ValueError(f"Potentially dangerous method call: {node.func.attr}")

    def _is_safe_import(self, module: str) -> bool:
        """Check if an import is from a safe module

        Only allow imports from specific safe modules to prevent
        execution of arbitrary system commands.

        Args:
            module: Module name to check

        Returns:
            True if module is safe, False otherwise
        """
        safe_prefixes = (
            'ia_modules.',
            'typing',
            'dataclasses',
            'datetime',
            'json',
            're',
            'math',
            'asyncio',
            'aiohttp',
            'pydantic',
            'enum',
            'abc',
            'collections',
            'itertools',
            'functools',
        )
        return any(module.startswith(prefix) for prefix in safe_prefixes)

    def _load_from_filesystem(self, module_path: str, class_name: str) -> Type[Step]:
        """Fallback to traditional filesystem import

        Args:
            module_path: Python module path
            class_name: Name of the step class

        Returns:
            Step class from filesystem

        Raises:
            ImportError: If module cannot be imported
            AttributeError: If class not found in module
        """
        import importlib

        try:
            module = importlib.import_module(module_path)
            step_class = getattr(module, class_name)

            # Validate it's a Step subclass
            if not issubclass(step_class, Step):
                raise TypeError(f"{class_name} is not a subclass of Step")

            return step_class
        except ImportError as e:
            raise ImportError(f"Cannot import module '{module_path}': {e}")
        except AttributeError as e:
            raise AttributeError(f"Module '{module_path}' has no class '{class_name}': {e}")

    def clear_cache(self):
        """Clear the step class cache

        Call this after updating step code in the database to ensure
        the new version is loaded on next execution.
        """
        if self.enable_cache:
            _step_class_cache.clear()
            logger.info("Cleared step class cache")


# Convenience function for backward compatibility
async def load_step_class_from_db(
    db_provider: DatabaseInterface,
    module_path: str,
    class_name: str,
    pipeline_id: Optional[str] = None,
    enable_cache: bool = True
) -> Type[Step]:
    """Load a step class from database with fallback to filesystem

    This is a convenience function that creates a DatabaseStepLoader
    and loads the step class in one call.

    Args:
        db_provider: Database interface for querying step modules
        module_path: Python module path
        class_name: Name of the step class
        pipeline_id: Optional pipeline ID to load pipeline-specific version
        enable_cache: Whether to cache loaded step classes

    Returns:
        Step class ready to be instantiated
    """
    loader = DatabaseStepLoader(db_provider, enable_cache=enable_cache)
    return await loader.load_step_class(module_path, class_name, pipeline_id)
