"""
Built-in tools for common operations.

Provides production-ready tools for web search, calculations,
code execution, file operations, and API calls.
"""

from .web_search import WebSearchTool, create_web_search_tool
from .calculator import CalculatorTool, create_calculator_tool
from .code_executor import CodeExecutorTool, create_code_executor_tool
from .file_ops import FileOperationsTool, create_file_ops_tool
from .api_caller import APICallerTool, create_api_caller_tool
try:
    from .web_scraper import WebScraperTool, create_web_scraper_tool, create_web_scraper_batch_tool
    _HAS_WEB_SCRAPER = True
except ImportError:  # aiohttp not installed
    _HAS_WEB_SCRAPER = False


__all__ = [
    "WebSearchTool",
    "create_web_search_tool",
    "CalculatorTool",
    "create_calculator_tool",
    "CodeExecutorTool",
    "create_code_executor_tool",
    "FileOperationsTool",
    "create_file_ops_tool",
    "APICallerTool",
    "create_api_caller_tool",
]

if _HAS_WEB_SCRAPER:
    __all__ += [
        "WebScraperTool",
        "create_web_scraper_tool",
        "create_web_scraper_batch_tool",
    ]


def register_all_builtin_tools(registry):
    """
    Register all built-in tools with a registry.

    Args:
        registry: Tool registry to register with

    Example:
        >>> from ia_modules.tools import AdvancedToolRegistry
        >>> from ia_modules.tools.builtin_tools import register_all_builtin_tools
        >>>
        >>> registry = AdvancedToolRegistry()
        >>> register_all_builtin_tools(registry)
    """
    # Web search
    registry.register_versioned(
        create_web_search_tool(),
        version="1.0.0",
        capabilities=["web_search", "research"],
        set_as_default=True
    )

    # Calculator
    registry.register_versioned(
        create_calculator_tool(),
        version="1.0.0",
        capabilities=["calculation", "math"],
        set_as_default=True
    )

    # Code executor
    registry.register_versioned(
        create_code_executor_tool(),
        version="1.0.0",
        capabilities=["code_execution", "data_processing"],
        set_as_default=True
    )

    # File operations
    registry.register_versioned(
        create_file_ops_tool(),
        version="1.0.0",
        capabilities=["file_operations", "data_storage"],
        set_as_default=True
    )

    # API caller
    registry.register_versioned(
        create_api_caller_tool(),
        version="1.0.0",
        capabilities=["api_call", "web_request"],
        set_as_default=True
    )

    # Web scraper (requires aiohttp)
    if _HAS_WEB_SCRAPER:
        registry.register_versioned(
            create_web_scraper_tool(),
            version="1.0.0",
            capabilities=["web_scraping", "content_extraction"],
            set_as_default=True
        )

        # Web scraper batch
        registry.register_versioned(
            create_web_scraper_batch_tool(),
            version="1.0.0",
            capabilities=["web_scraping", "batch_processing", "content_extraction"],
            set_as_default=True
        )
