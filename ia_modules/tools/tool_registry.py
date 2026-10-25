"""
Enhanced tool registry with versioning, capability indexing, and caching.

Extends the basic tool registry with advanced features for production use.
"""

import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set
from collections import defaultdict

from .core import ToolDefinition


@dataclass
class ToolVersion:
    """
    Version information for a tool.

    Attributes:
        version: Semantic version string (e.g., "1.0.0")
        tool: Tool definition
        deprecated: Whether this version is deprecated
        deprecation_message: Message explaining deprecation
        created_at: When this version was registered
    """
    version: str
    tool: ToolDefinition
    deprecated: bool = False
    deprecation_message: Optional[str] = None
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class CacheEntry:
    """
    Cache entry for tool results.

    Attributes:
        result: Cached result
        timestamp: When result was cached
        ttl: Time to live in seconds
        hit_count: Number of times this entry was retrieved
    """
    result: Any
    timestamp: datetime
    ttl: float
    hit_count: int = 0

    def is_valid(self) -> bool:
        """Check if cache entry is still valid."""
        if self.ttl <= 0:
            return True  # No expiration

        # Handle both timezone-aware and naive datetimes
        # Use the same "now" type as timestamp for consistent comparison
        if self.timestamp.tzinfo is None:
            # Timestamp is naive (local time), use naive now
            now = datetime.now()
        else:
            # Timestamp is aware, use aware now
            now = datetime.now(timezone.utc)

        elapsed = (now - self.timestamp).total_seconds()
        return elapsed < self.ttl


@dataclass
class ToolCapability:
    """
    Describes a capability that tools can provide.

    Attributes:
        name: Capability name (e.g., "web_search", "data_processing")
        description: Human-readable description
        tags: Additional categorization tags
    """
    name: str
    description: str
    tags: Set[str] = field(default_factory=set)


class AdvancedToolRegistry:
    """
    Enhanced tool registry with versioning, caching, and capability indexing.

    Features:
    - Tool versioning with semantic versioning support
    - Result caching with TTL
    - Capability-based tool discovery
    - Usage statistics and analytics
    - Tool deprecation handling
    - Performance metrics

    Example:
        >>> registry = AdvancedToolRegistry()
        >>>
        >>> # Register tool with version
        >>> registry.register_versioned(tool, version="1.0.0", capabilities=["web_search"])
        >>>
        >>> # Find tools by capability
        >>> search_tools = registry.find_by_capability("web_search")
        >>>
        >>> # Execute with caching
        >>> result = await registry.execute_cached(
        ...     "web_search", {"query": "AI"}, ttl=3600
        ... )
    """

    def __init__(self, enable_caching: bool = True):
        """
        Initialize advanced tool registry.

        Args:
            enable_caching: Whether to enable result caching
        """
        # Tool storage: name -> {version -> ToolVersion}
        self.tools: Dict[str, Dict[str, ToolVersion]] = defaultdict(dict)

        # Default version for each tool
        self.default_versions: Dict[str, str] = {}

        # Capability index: capability -> set of (tool_name, version)
        self.capability_index: Dict[str, Set[tuple[str, str]]] = defaultdict(set)

        # Result cache: cache_key -> CacheEntry
        self.cache: Dict[str, CacheEntry] = {}
        self.enable_caching = enable_caching

        # Statistics
        self.execution_stats: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "total_duration": 0.0,
                "cache_hits": 0,
                "cache_misses": 0
            }
        )

        self.logger = logging.getLogger("AdvancedToolRegistry")

    def register_versioned(
        self,
        tool: ToolDefinition,
        version: str = "1.0.0",
        capabilities: Optional[List[str]] = None,
        set_as_default: bool = True
    ) -> None:
        """
        Register a versioned tool.

        Args:
            tool: Tool definition
            version: Semantic version string
            capabilities: List of capability names this tool provides
            set_as_default: Whether to set this as default version
        """
        tool_version = ToolVersion(version=version, tool=tool)
        self.tools[tool.name][version] = tool_version

        if set_as_default or tool.name not in self.default_versions:
            self.default_versions[tool.name] = version

        # Index by capabilities
        if capabilities:
            for capability in capabilities:
                self.capability_index[capability].add((tool.name, version))

        # Initialize execution statistics for this tool if not exists
        if tool.name not in self.execution_stats:
            self.execution_stats[tool.name] = {
                "total_calls": 0,
                "successful_calls": 0,
                "failed_calls": 0,
                "total_duration": 0.0,
                "avg_execution_time": 0.0,
                "cache_hits": 0,
                "cache_misses": 0
            }

        self.logger.info(f"Registered {tool.name} v{version}")

    def register(self, tool: ToolDefinition, capabilities: Optional[List[str]] = None) -> None:
        """
        Register tool without explicit versioning (uses 1.0.0).

        Args:
            tool: Tool definition
            capabilities: List of capability names
        """
        self.register_versioned(tool, version="1.0.0", capabilities=capabilities)

    def get_tool(self, name: str, version: Optional[str] = None) -> Optional[ToolDefinition]:
        """
        Get tool by name and optional version.

        Args:
            name: Tool name
            version: Specific version, or None for default

        Returns:
            ToolDefinition or None if not found
        """
        if name not in self.tools:
            return None

        if version is None:
            version = self.default_versions.get(name)
            if version is None:
                return None

        tool_version = self.tools[name].get(version)
        return tool_version.tool if tool_version else None

    def list_versions(self, tool_name: str) -> List[str]:
        """
        List all versions of a tool.

        Args:
            tool_name: Tool name

        Returns:
            List of version strings
        """
        return list(self.tools.get(tool_name, {}).keys())

    def deprecate_version(
        self,
        tool_name: str,
        version: str,
        message: str = "This version is deprecated"
    ) -> bool:
        """
        Mark a tool version as deprecated.

        Args:
            tool_name: Tool name
            version: Version to deprecate
            message: Deprecation message

        Returns:
            True if deprecated, False if not found
        """
        if tool_name in self.tools and version in self.tools[tool_name]:
            self.tools[tool_name][version].deprecated = True
            self.tools[tool_name][version].deprecation_message = message
            self.logger.warning(f"Deprecated {tool_name} v{version}: {message}")
            return True
        return False

    def find_by_capability(
        self,
        capability: str,
        include_deprecated: bool = False
    ) -> List[tuple[str, str, ToolDefinition]]:
        """
        Find tools by capability.

        Args:
            capability: Capability name
            include_deprecated: Whether to include deprecated versions

        Returns:
            List of (tool_name, version, tool_definition) tuples
        """
        results = []

        for tool_name, version in self.capability_index.get(capability, set()):
            tool_version = self.tools[tool_name][version]

            if not include_deprecated and tool_version.deprecated:
                continue

            results.append((tool_name, version, tool_version.tool))

        return results

    def _generate_cache_key(self, tool_name: str, parameters: Dict[str, Any]) -> str:
        """
        Generate cache key for tool execution.

        Args:
            tool_name: Tool name
            parameters: Tool parameters

        Returns:
            Cache key string
        """
        # Sort parameters for consistent hashing
        param_str = json.dumps(parameters, sort_keys=True)
        key_str = f"{tool_name}:{param_str}"
        return hashlib.sha256(key_str.encode()).hexdigest()

    async def execute(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        version: Optional[str] = None
    ) -> Any:
        """
        Execute a tool.

        Args:
            tool_name: Tool name
            parameters: Tool parameters
            version: Specific version or None for default

        Returns:
            Tool execution result

        Raises:
            ValueError: If tool not found or parameters invalid
        """
        import time

        tool = self.get_tool(tool_name, version)
        if tool is None:
            raise ValueError(f"Tool not found: {tool_name}" + (f" v{version}" if version else ""))

        # Check if deprecated
        version_to_use = version or self.default_versions.get(tool_name)
        if version_to_use and self.tools[tool_name][version_to_use].deprecated:
            deprecation_msg = self.tools[tool_name][version_to_use].deprecation_message
            self.logger.warning(f"Using deprecated tool {tool_name} v{version_to_use}: {deprecation_msg}")

        # Validate parameters
        is_valid, error = tool.validate_parameters(parameters)
        if not is_valid:
            raise ValueError(f"Invalid parameters: {error}")

        # Track execution
        start_time = time.time()
        stats = self.execution_stats[tool_name]
        stats["total_calls"] += 1

        try:
            result = await tool.function(**parameters)
            stats["successful_calls"] += 1
            stats["total_duration"] += time.time() - start_time
            return result

        except Exception:
            stats["failed_calls"] += 1
            stats["total_duration"] += time.time() - start_time
            raise

    async def execute_cached(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        ttl: float = 3600.0,
        version: Optional[str] = None
    ) -> Any:
        """
        Execute tool with result caching.

        Args:
            tool_name: Tool name
            parameters: Tool parameters
            ttl: Cache time-to-live in seconds (0 for no expiration)
            version: Specific version or None for default

        Returns:
            Tool execution result (cached or fresh)
        """
        if not self.enable_caching:
            return await self.execute(tool_name, parameters, version)

        cache_key = self._generate_cache_key(tool_name, parameters)
        stats = self.execution_stats[tool_name]

        # Check cache
        if cache_key in self.cache:
            entry = self.cache[cache_key]
            if entry.is_valid():
                entry.hit_count += 1
                stats["cache_hits"] += 1
                self.logger.debug(f"Cache hit for {tool_name}")
                return entry.result

        # Cache miss - execute tool
        stats["cache_misses"] += 1
        result = await self.execute(tool_name, parameters, version)

        # Store in cache
        self.cache[cache_key] = CacheEntry(
            result=result,
            timestamp=datetime.now(timezone.utc),
            ttl=ttl
        )

        return result

    def clear_cache(self, tool_name: Optional[str] = None) -> int:
        """
        Clear cache entries.

        Args:
            tool_name: Specific tool to clear, or None for all

        Returns:
            Number of entries cleared
        """
        if tool_name is None:
            count = len(self.cache)
            self.cache.clear()
            self.logger.info(f"Cleared all cache ({count} entries)")
            return count

        # Clear specific tool's cache
        keys_to_remove = []
        for key, entry in self.cache.items():
            # Need to check if key belongs to tool_name
            # This is approximate since we hash the key
            keys_to_remove.append(key)

        for key in keys_to_remove:
            del self.cache[key]

        self.logger.info(f"Cleared cache for {tool_name} ({len(keys_to_remove)} entries)")
        return len(keys_to_remove)

    def cleanup_expired_cache(self) -> int:
        """
        Remove expired cache entries.

        Returns:
            Number of entries removed
        """
        keys_to_remove = [
            key for key, entry in self.cache.items()
            if not entry.is_valid()
        ]

        for key in keys_to_remove:
            del self.cache[key]

        if keys_to_remove:
            self.logger.info(f"Removed {len(keys_to_remove)} expired cache entries")

        return len(keys_to_remove)

    def get_statistics(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """
        Get execution statistics.

        Args:
            tool_name: Specific tool or None for all

        Returns:
            Statistics dictionary
        """
        if tool_name:
            return dict(self.execution_stats.get(tool_name, {}))

        return {
            name: dict(stats)
            for name, stats in self.execution_stats.items()
        }

    def list_capabilities(self) -> List[str]:
        """
        List all registered capabilities.

        Returns:
            List of capability names
        """
        return list(self.capability_index.keys())

    def list_tools(
        self,
        include_deprecated: bool = False,
        capability: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        List registered tools.

        Args:
            include_deprecated: Whether to include deprecated versions
            capability: Filter by capability

        Returns:
            List of tool information dictionaries
        """
        results = []

        if capability:
            # Filter by capability
            tools_with_cap = self.find_by_capability(capability, include_deprecated)
            for tool_name, version, tool in tools_with_cap:
                tool_version = self.tools[tool_name][version]
                results.append({
                    "name": tool_name,
                    "version": version,
                    "description": tool.description,
                    "deprecated": tool_version.deprecated,
                    "deprecation_message": tool_version.deprecation_message,
                    "is_default": self.default_versions.get(tool_name) == version
                })
        else:
            # All tools
            for tool_name, versions in self.tools.items():
                for version, tool_version in versions.items():
                    if not include_deprecated and tool_version.deprecated:
                        continue

                    results.append({
                        "name": tool_name,
                        "version": version,
                        "description": tool_version.tool.description,
                        "deprecated": tool_version.deprecated,
                        "deprecation_message": tool_version.deprecation_message,
                        "is_default": self.default_versions.get(tool_name) == version
                    })

        return results

    def export_tool_catalog(self) -> Dict[str, Any]:
        """
        Export complete tool catalog with metadata.

        Returns:
            Catalog dictionary
        """
        return {
            "tools": self.list_tools(include_deprecated=True),
            "capabilities": self.list_capabilities(),
            "statistics": self.get_statistics(),
            "cache_size": len(self.cache),
            "total_tools": sum(len(versions) for versions in self.tools.values())
        }
