"""
Unit tests for advanced tool system.

Tests tool registry, tool chains, and parallel execution.
"""

import pytest
import asyncio
from datetime import datetime

from ia_modules.tools.tool_registry import (
    AdvancedToolRegistry,
    ToolVersion,
    CacheEntry,
    ToolCapability
)
from ia_modules.tools.tool_chain import (
    ToolChain,
    ChainStep,
    ChainResult
)
from ia_modules.tools.parallel_executor import (
    ParallelExecutor,
    ExecutionTask,
    ExecutionStatus,
    ResourceLimits
)
from ia_modules.tools.core import ToolDefinition


# Mock tool for testing
async def mock_tool(**kwargs):
    """Mock tool function."""
    await asyncio.sleep(0.01)
    return {"result": "success", "input": kwargs}


def create_mock_tool(name, description="Test tool"):
    """Create a mock ToolDefinition."""
    return ToolDefinition(
        name=name,
        description=description,
        function=mock_tool,
        parameters={}
    )


class TestToolVersion:
    """Test ToolVersion dataclass."""

    def test_creation(self):
        """ToolVersion can be created."""
        tool = create_mock_tool("test")
        version = ToolVersion(version="1.0.0", tool=tool)

        assert version.version == "1.0.0"
        assert version.tool == tool
        assert version.deprecated is False
        assert version.deprecation_message is None
        assert version.created_at is not None


class TestCacheEntry:
    """Test CacheEntry dataclass."""

    def test_creation(self):
        """CacheEntry can be created."""
        now = datetime.now()
        entry = CacheEntry(
            result={"data": "test"},
            timestamp=now,
            ttl=3600.0
        )

        assert entry.result == {"data": "test"}
        assert entry.timestamp == now
        assert entry.ttl == 3600.0
        assert entry.hit_count == 0

    def test_is_valid_no_ttl(self):
        """Entry with no TTL is always valid."""
        entry = CacheEntry(
            result="test",
            timestamp=datetime.now(),
            ttl=0
        )

        assert entry.is_valid() is True

    def test_is_valid_within_ttl(self):
        """Entry is valid within TTL."""
        entry = CacheEntry(
            result="test",
            timestamp=datetime.now(),
            ttl=3600.0
        )

        assert entry.is_valid() is True


class TestToolCapability:
    """Test ToolCapability dataclass."""

    def test_creation(self):
        """ToolCapability can be created."""
        capability = ToolCapability(
            name="web_search",
            description="Search the web",
            tags={"search", "internet"}
        )

        assert capability.name == "web_search"
        assert capability.description == "Search the web"
        assert "search" in capability.tags


class TestAdvancedToolRegistry:
    """Test AdvancedToolRegistry functionality."""

    @pytest.fixture
    def registry(self):
        """Create tool registry instance."""
        return AdvancedToolRegistry(enable_caching=True)

    @pytest.fixture
    def mock_tool_def(self):
        """Create mock tool definition."""
        return create_mock_tool("test_tool", "A test tool")

    def test_creation(self, registry):
        """AdvancedToolRegistry can be created."""
        assert registry.enable_caching is True
        assert len(registry.tools) == 0
        assert len(registry.cache) == 0

    def test_register_versioned(self, registry, mock_tool_def):
        """Can register versioned tool."""
        registry.register_versioned(
            tool=mock_tool_def,
            version="1.0.0",
            capabilities=["testing"]
        )

        assert "test_tool" in registry.tools
        assert "1.0.0" in registry.tools["test_tool"]
        assert registry.default_versions["test_tool"] == "1.0.0"

    def test_register_without_version(self, registry, mock_tool_def):
        """Can register tool without explicit version."""
        registry.register(mock_tool_def, capabilities=["testing"])

        assert "test_tool" in registry.tools
        assert "1.0.0" in registry.tools["test_tool"]

    def test_register_multiple_versions(self, registry):
        """Can register multiple versions of same tool."""
        tool_v1 = create_mock_tool("tool", "Version 1")
        tool_v2 = create_mock_tool("tool", "Version 2")

        registry.register_versioned(tool_v1, version="1.0.0")
        registry.register_versioned(tool_v2, version="2.0.0")

        assert len(registry.tools["tool"]) == 2
        assert "1.0.0" in registry.tools["tool"]
        assert "2.0.0" in registry.tools["tool"]

    def test_get_tool_default_version(self, registry, mock_tool_def):
        """Can get tool with default version."""
        registry.register_versioned(mock_tool_def, version="1.0.0")

        tool = registry.get_tool("test_tool")

        assert tool == mock_tool_def

    def test_get_tool_specific_version(self, registry):
        """Can get specific tool version."""
        tool_v1 = create_mock_tool("tool", "V1")
        tool_v2 = create_mock_tool("tool", "V2")

        registry.register_versioned(tool_v1, version="1.0.0")
        registry.register_versioned(tool_v2, version="2.0.0")

        tool = registry.get_tool("tool", version="1.0.0")

        assert tool == tool_v1

    def test_get_tool_nonexistent(self, registry):
        """Getting nonexistent tool returns None."""
        tool = registry.get_tool("nonexistent")

        assert tool is None

    def test_list_versions(self, registry):
        """Can list tool versions."""
        tool = create_mock_tool("tool")
        registry.register_versioned(tool, version="1.0.0")
        registry.register_versioned(tool, version="1.1.0")
        registry.register_versioned(tool, version="2.0.0")

        versions = registry.list_versions("tool")

        assert len(versions) == 3
        assert "1.0.0" in versions
        assert "2.0.0" in versions

    def test_deprecate_version(self, registry, mock_tool_def):
        """Can deprecate tool version."""
        registry.register_versioned(mock_tool_def, version="1.0.0")

        success = registry.deprecate_version(
            "test_tool",
            "1.0.0",
            "Please use 2.0.0"
        )

        assert success is True
        tool_version = registry.tools["test_tool"]["1.0.0"]
        assert tool_version.deprecated is True
        assert "2.0.0" in tool_version.deprecation_message

    def test_deprecate_nonexistent_version(self, registry):
        """Deprecating nonexistent version returns False."""
        success = registry.deprecate_version("nonexistent", "1.0.0")

        assert success is False

    def test_find_by_capability(self, registry):
        """Can find tools by capability."""
        tool1 = create_mock_tool("search_tool")
        tool2 = create_mock_tool("analyze_tool")

        registry.register_versioned(
            tool1,
            version="1.0.0",
            capabilities=["search", "web"]
        )
        registry.register_versioned(
            tool2,
            version="1.0.0",
            capabilities=["analysis"]
        )

        search_tools = registry.find_by_capability("search")

        assert len(search_tools) == 1
        assert search_tools[0][0] == "search_tool"

    def test_find_by_capability_exclude_deprecated(self, registry):
        """Finding by capability excludes deprecated by default."""
        tool = create_mock_tool("tool")

        registry.register_versioned(
            tool,
            version="1.0.0",
            capabilities=["test"]
        )
        registry.deprecate_version("tool", "1.0.0")

        results = registry.find_by_capability("test", include_deprecated=False)

        assert len(results) == 0

        results_with_deprecated = registry.find_by_capability(
            "test",
            include_deprecated=True
        )

        assert len(results_with_deprecated) == 1

    async def test_execute_tool(self, registry, mock_tool_def):
        """Can execute tool."""
        registry.register_versioned(mock_tool_def, version="1.0.0")

        result = await registry.execute(
            "test_tool",
            {"param1": "value1"}
        )

        assert result is not None
        assert result["result"] == "success"

    async def test_execute_nonexistent_tool(self, registry):
        """Executing nonexistent tool raises error."""
        with pytest.raises(ValueError, match="Tool not found"):
            await registry.execute("nonexistent", {})

    async def test_execute_cached(self, registry, mock_tool_def):
        """Can execute with caching."""
        registry.register_versioned(mock_tool_def, version="1.0.0")

        # First call
        result1 = await registry.execute_cached(
            "test_tool",
            {"param": "value"},
            ttl=3600
        )

        # Second call (should be cached)
        result2 = await registry.execute_cached(
            "test_tool",
            {"param": "value"},
            ttl=3600
        )

        assert result1 == result2

        # Check cache statistics
        stats = registry.get_statistics("test_tool")
        assert stats["cache_hits"] > 0

    async def test_execute_cached_disabled(self):
        """Caching can be disabled."""
        registry = AdvancedToolRegistry(enable_caching=False)
        tool = create_mock_tool("tool")

        registry.register_versioned(tool, version="1.0.0")

        await registry.execute_cached("tool", {})

        # Should not cache
        assert len(registry.cache) == 0

    def test_clear_cache(self, registry, mock_tool_def):
        """Can clear cache."""
        registry.cache["key1"] = CacheEntry(
            result="test",
            timestamp=datetime.now(),
            ttl=3600
        )

        count = registry.clear_cache()

        assert count == 1
        assert len(registry.cache) == 0

    def test_cleanup_expired_cache(self, registry):
        """Can cleanup expired cache entries."""
        from datetime import timedelta

        # Add expired entry
        expired_time = datetime.now() - timedelta(hours=2)
        registry.cache["expired"] = CacheEntry(
            result="old",
            timestamp=expired_time,
            ttl=3600  # 1 hour TTL, but 2 hours old
        )

        # Add valid entry
        registry.cache["valid"] = CacheEntry(
            result="new",
            timestamp=datetime.now(),
            ttl=3600
        )

        removed = registry.cleanup_expired_cache()

        assert removed == 1
        assert "valid" in registry.cache
        assert "expired" not in registry.cache

    def test_get_statistics(self, registry, mock_tool_def):
        """Can get execution statistics."""
        registry.register_versioned(mock_tool_def, version="1.0.0")

        stats = registry.get_statistics("test_tool")

        assert "total_calls" in stats
        assert "successful_calls" in stats
        assert "failed_calls" in stats

    def test_list_capabilities(self, registry):
        """Can list all capabilities."""
        tool1 = create_mock_tool("tool1")
        tool2 = create_mock_tool("tool2")

        registry.register_versioned(tool1, capabilities=["search"])
        registry.register_versioned(tool2, capabilities=["analysis"])

        capabilities = registry.list_capabilities()

        assert "search" in capabilities
        assert "analysis" in capabilities

    def test_list_tools(self, registry):
        """Can list registered tools."""
        tool = create_mock_tool("tool")
        registry.register_versioned(tool, version="1.0.0")

        tools = registry.list_tools()

        assert len(tools) > 0
        assert tools[0]["name"] == "tool"

    def test_export_tool_catalog(self, registry, mock_tool_def):
        """Can export complete tool catalog."""
        registry.register_versioned(
            mock_tool_def,
            version="1.0.0",
            capabilities=["testing"]
        )

        catalog = registry.export_tool_catalog()

        assert "tools" in catalog
        assert "capabilities" in catalog
        assert "statistics" in catalog
        assert catalog["total_tools"] > 0


class TestChainStep:
    """Test ChainStep dataclass."""

    def test_creation(self):
        """ChainStep can be created."""
        step = ChainStep(
            tool_name="web_search",
            input_mapping={"query": "user_input"},
            output_key="search_results"
        )

        assert step.tool_name == "web_search"
        assert step.input_mapping == {"query": "user_input"}
        assert step.output_key == "search_results"
        assert step.on_error == "raise"


class TestToolChain:
    """Test ToolChain functionality."""

    @pytest.fixture
    async def tool_executor(self):
        """Create mock tool executor."""
        async def executor(tool_name, parameters):
            await asyncio.sleep(0.01)
            return f"result_{tool_name}"
        return executor

    @pytest.fixture
    def chain(self, tool_executor):
        """Create tool chain instance."""
        return ToolChain(tool_executor)

    def test_creation(self, chain):
        """ToolChain can be created."""
        assert len(chain.steps) == 0

    def test_add_step(self, chain):
        """Can add step to chain."""
        chain.add_step(
            tool_name="tool1",
            input_mapping={"param": "input"},
            output_key="output1"
        )

        assert len(chain.steps) == 1
        assert chain.steps[0].tool_name == "tool1"

    def test_add_step_method_chaining(self, chain):
        """add_step supports method chaining."""
        result = chain.add_step(
            "tool1",
            {"p": "i"},
            "o1"
        ).add_step(
            "tool2",
            {"p": "o1"},
            "o2"
        )

        assert result == chain
        assert len(chain.steps) == 2

    async def test_execute_simple_chain(self, chain):
        """Can execute simple chain."""
        chain.add_step("tool1", {}, "output1")
        chain.add_step("tool2", {}, "output2")

        result = await chain.execute({})

        assert isinstance(result, ChainResult)
        assert result.success is True
        assert "output1" in result.context
        assert "output2" in result.context

    async def test_execute_with_input_mapping(self, tool_executor):
        """Chain maps inputs correctly."""
        executed_params = []

        async def tracking_executor(tool_name, parameters):
            executed_params.append((tool_name, parameters))
            return "result"

        chain = ToolChain(tracking_executor)
        chain.add_step(
            "tool1",
            {"query": "user_query"},
            "result1"
        )

        await chain.execute({"user_query": "test"})

        assert len(executed_params) == 1
        assert executed_params[0][1]["query"] == "test"


class TestParallelExecutor:
    """Test ParallelExecutor functionality."""

    @pytest.fixture
    async def tool_executor(self):
        """Create mock tool executor."""
        async def executor(tool_name, parameters):
            await asyncio.sleep(0.01)
            return f"result_{tool_name}"
        return executor

    @pytest.fixture
    def executor(self, tool_executor):
        """Create parallel executor instance."""
        return ParallelExecutor(
            tool_executor=tool_executor,
            resource_limits=ResourceLimits(max_concurrent=5)
        )

    def test_creation(self, executor):
        """ParallelExecutor can be created."""
        assert executor.resource_limits.max_concurrent == 5
        assert len(executor.tasks) == 0

    def test_add_task(self, executor):
        """Can add task to executor."""
        executor.add_task(
            task_id="task1",
            tool_name="tool1",
            parameters={"param": "value"}
        )

        assert "task1" in executor.tasks
        assert executor.tasks["task1"].status == ExecutionStatus.PENDING

    def test_add_task_with_dependencies(self, executor):
        """Can add task with dependencies."""
        executor.add_task("task1", "tool1", {})
        executor.add_task(
            "task2",
            "tool2",
            {},
            dependencies=["task1"]
        )

        assert "task1" in executor.tasks["task2"].dependencies

    def test_add_duplicate_task(self, executor):
        """Adding duplicate task raises error."""
        executor.add_task("task1", "tool1", {})

        with pytest.raises(ValueError, match="already exists"):
            executor.add_task("task1", "tool2", {})

    async def test_execute_all_simple(self, executor):
        """Can execute all tasks."""
        executor.add_task("task1", "tool1", {})
        executor.add_task("task2", "tool2", {})

        results = await executor.execute_all()

        assert len(results) == 2
        assert "task1" in results
        assert "task2" in results

    async def test_execute_all_with_dependencies(self, executor):
        """Tasks execute in dependency order."""
        executor.add_task("task1", "tool1", {})
        executor.add_task("task2", "tool2", {}, dependencies=["task1"])

        await executor.execute_all()

        task1 = executor.tasks["task1"]
        task2 = executor.tasks["task2"]

        # Task2 should complete after task1
        assert task1.completed_at <= task2.started_at


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_registry_generate_cache_key(self):
        """Cache key generation is consistent."""
        registry = AdvancedToolRegistry()

        key1 = registry._generate_cache_key("tool", {"a": 1, "b": 2})
        key2 = registry._generate_cache_key("tool", {"b": 2, "a": 1})

        # Should be same regardless of parameter order
        assert key1 == key2

    @pytest.mark.asyncio
    async def test_chain_empty_execute(self):
        """Empty chain executes successfully."""
        async def executor(tool, params):
            return "result"

        chain = ToolChain(executor)
        result = await chain.execute({})

        assert result.success is True

    @pytest.mark.asyncio
    async def test_parallel_executor_no_tasks(self):
        """Parallel executor with no tasks."""
        async def executor(tool, params):
            return "result"

        pe = ParallelExecutor(executor)
        results = await pe.execute_all()

        assert results == {}


class TestResourceLimits:
    """Test ResourceLimits dataclass."""

    def test_creation_defaults(self):
        """ResourceLimits has proper defaults."""
        limits = ResourceLimits()

        assert limits.max_concurrent == 10
        assert limits.max_memory_mb == 0
        assert limits.max_cpu_percent == 0
        assert limits.timeout_seconds == 300.0

    def test_creation_custom(self):
        """ResourceLimits can be customized."""
        limits = ResourceLimits(
            max_concurrent=5,
            timeout_seconds=60.0
        )

        assert limits.max_concurrent == 5
        assert limits.timeout_seconds == 60.0


class TestExecutionTask:
    """Test ExecutionTask dataclass."""

    def test_creation(self):
        """ExecutionTask can be created."""
        task = ExecutionTask(
            task_id="test",
            tool_name="tool",
            parameters={"param": "value"}
        )

        assert task.task_id == "test"
        assert task.status == ExecutionStatus.PENDING
        assert task.result is None
        assert task.error is None
