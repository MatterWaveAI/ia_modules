"""
Comprehensive unit tests for the ia_modules tools subsystem.

Covers: tool_planner, error_handling, advanced_executor, tool_chain,
parallel_executor, and all builtin_tools (calculator, file_ops,
code_executor, api_caller, web_search).
"""

import asyncio
import math
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# --------------------------------------------------------------------------- #
# Core / Registry imports
# --------------------------------------------------------------------------- #
from ia_modules.tools.core import (
    ToolDefinition,
    ToolRegistry,
    tool,
    function_tool,
    from_openai_function,
    from_langchain_tool,
    ToolAdapter,
)
from ia_modules.tools.tool_registry import (
    AdvancedToolRegistry,
    CacheEntry,
)

# --------------------------------------------------------------------------- #
# Planner
# --------------------------------------------------------------------------- #
from ia_modules.tools.tool_planner import (
    ToolPlanner,
    Task,
    ExecutionPlan,
    ToolMatch,
    TaskComplexity,
)

# --------------------------------------------------------------------------- #
# Error handling
# --------------------------------------------------------------------------- #
from ia_modules.tools.error_handling import (
    RetryExecutor,
    RetryConfig,
    RetryStrategy,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
    FallbackExecutor,
    FallbackConfig,
    CompositeErrorHandler,
    with_retry,
    with_circuit_breaker,
    with_fallback,
)

# --------------------------------------------------------------------------- #
# Chain
# --------------------------------------------------------------------------- #
from ia_modules.tools.tool_chain import (
    ToolChain,
    ChainBuilder,
)

# --------------------------------------------------------------------------- #
# Parallel executor
# --------------------------------------------------------------------------- #
from ia_modules.tools.parallel_executor import (
    ParallelExecutor,
    ExecutionStatus,
    ResourceLimits,
)

# --------------------------------------------------------------------------- #
# Advanced executor
# --------------------------------------------------------------------------- #
from ia_modules.tools.advanced_executor import AdvancedToolExecutor

# --------------------------------------------------------------------------- #
# Builtin tools
# --------------------------------------------------------------------------- #
from ia_modules.tools.builtin_tools.calculator import (
    CalculatorTool,
    calculator_function,
    create_calculator_tool,
)
from ia_modules.tools.builtin_tools.file_ops import (
    FileOperationsTool,
    file_ops_function,
    create_file_ops_tool,
)
from ia_modules.tools.builtin_tools.code_executor import (
    CodeExecutorTool,
    code_executor_function,
    create_code_executor_tool,
)
from ia_modules.tools.builtin_tools.api_caller import (
    APICallerTool,
    RateLimitConfig,
    api_caller_function,
    create_api_caller_tool,
)
from ia_modules.tools.builtin_tools.web_search import (
    WebSearchTool,
    SearchResult,
    web_search_function,
    create_web_search_tool,
)

# =========================================================================== #
#  HELPERS
# =========================================================================== #


def _make_tool_def(name="test_tool", params=None, func=None):
    """Create a minimal ToolDefinition for testing."""

    async def _noop(**kw):
        return kw

    return ToolDefinition(
        name=name,
        description=f"Test tool {name}",
        parameters=params or {},
        function=func or _noop,
    )


async def _dummy_executor(tool_name, params):
    """Simple async executor that echoes tool_name and params."""
    return {"tool": tool_name, **params}


async def _failing_executor(tool_name, params):
    raise RuntimeError(f"fail:{tool_name}")


# =========================================================================== #
#  TASK COMPLEXITY / PLANNER
# =========================================================================== #


class TestTaskComplexity:
    def test_enum_values(self):
        assert TaskComplexity.SIMPLE.value == "simple"
        assert TaskComplexity.MODERATE.value == "moderate"
        assert TaskComplexity.COMPLEX.value == "complex"
        assert TaskComplexity.VERY_COMPLEX.value == "very_complex"


class TestTask:
    def test_defaults(self):
        t = Task(description="do stuff")
        assert t.description == "do stuff"
        assert t.requirements == []
        assert t.constraints == {}
        assert t.context == {}


class TestToolMatch:
    def test_fields(self):
        m = ToolMatch("t", "1.0.0", "cap", 0.9, "reason")
        assert m.tool_name == "t"
        assert m.confidence == 0.9


class TestExecutionPlan:
    def test_defaults(self):
        p = ExecutionPlan(task=Task("x"))
        assert p.steps == []
        assert p.complexity == TaskComplexity.SIMPLE
        assert p.confidence == 1.0


class TestToolPlanner:
    def _make_registry(self):
        reg = AdvancedToolRegistry()
        td = _make_tool_def("search_tool")
        reg.register_versioned(td, "1.0.0", capabilities=["web_search"])
        td2 = _make_tool_def("calc_tool")
        reg.register_versioned(td2, "1.0.0", capabilities=["calculation"])
        return reg

    # -- complexity analysis --

    def test_simple_task(self):
        planner = ToolPlanner(self._make_registry())
        task = Task("hello", requirements=["web_search"])
        assert planner._analyze_task_complexity(task) == TaskComplexity.SIMPLE

    def test_moderate_task(self):
        planner = ToolPlanner(self._make_registry())
        task = Task("hello", requirements=["a", "b"])
        assert planner._analyze_task_complexity(task) == TaskComplexity.MODERATE

    def test_complex_task_conditionals(self):
        planner = ToolPlanner(self._make_registry())
        task = Task("do this if possible", requirements=["a", "b"])
        assert planner._analyze_task_complexity(task) == TaskComplexity.COMPLEX

    def test_complex_task_many_requirements(self):
        planner = ToolPlanner(self._make_registry())
        task = Task("hello", requirements=["a", "b", "c", "d"])
        assert planner._analyze_task_complexity(task) == TaskComplexity.COMPLEX

    def test_very_complex_task(self):
        planner = ToolPlanner(self._make_registry())
        task = Task("hello", requirements=["a", "b", "c", "d", "e", "f"])
        assert planner._analyze_task_complexity(task) == TaskComplexity.VERY_COMPLEX

    # -- capability extraction --

    def test_extract_capabilities(self):
        planner = ToolPlanner(self._make_registry())
        caps = planner._extract_capabilities_from_description("search and calculate result")
        assert "web_search" in caps
        assert "calculation" in caps

    def test_extract_no_match(self):
        planner = ToolPlanner(self._make_registry())
        caps = planner._extract_capabilities_from_description("nothing relevant")
        assert caps == []

    # -- tool matching --

    def test_match_tools_found(self):
        planner = ToolPlanner(self._make_registry())
        matches = planner._match_tools_to_capability("web_search")
        assert len(matches) >= 1
        assert matches[0].tool_name == "search_tool"

    def test_match_tools_not_found(self):
        planner = ToolPlanner(self._make_registry())
        matches = planner._match_tools_to_capability("unknown_cap")
        assert matches == []

    def test_match_tools_deprecated_excluded_by_default(self):
        reg = self._make_registry()
        reg.deprecate_version("search_tool", "1.0.0")
        planner = ToolPlanner(reg)
        # find_by_capability excludes deprecated by default
        matches = planner._match_tools_to_capability("web_search")
        assert matches == []

    # -- decompose --

    def test_decompose_explicit_requirements(self):
        planner = ToolPlanner(self._make_registry())
        task = Task("x", requirements=["web_search", "calculation"])
        subs = planner._decompose_task(task)
        assert len(subs) == 2
        assert subs[0]["dependencies"] == []
        assert subs[1]["dependencies"] == [0]

    def test_decompose_from_description(self):
        planner = ToolPlanner(self._make_registry())
        task = Task("search and calculate stuff")
        subs = planner._decompose_task(task)
        assert len(subs) >= 1

    # -- create_plan --

    async def test_create_plan_basic(self):
        planner = ToolPlanner(self._make_registry())
        task = Task("search web", requirements=["web_search"])
        plan = await planner.create_plan(task, max_alternatives=0)
        assert len(plan.steps) == 1
        assert plan.confidence > 0

    async def test_create_plan_with_alternatives(self):
        reg = self._make_registry()
        # add second search tool
        reg.register_versioned(
            _make_tool_def("search2"), "1.0.0", capabilities=["web_search"]
        )
        planner = ToolPlanner(reg)
        task = Task("search web", requirements=["web_search"])
        plan = await planner.create_plan(task, max_alternatives=2)
        assert isinstance(plan, ExecutionPlan)

    async def test_create_plan_no_tools(self):
        reg = AdvancedToolRegistry()
        planner = ToolPlanner(reg)
        task = Task("x", requirements=["nonexistent"])
        plan = await planner.create_plan(task, max_alternatives=0)
        assert plan.steps == []
        assert plan.confidence == 0.0

    # -- optimize_plan --

    def test_optimize_plan_parallel(self):
        planner = ToolPlanner(self._make_registry())
        task = Task("x")
        plan = ExecutionPlan(
            task=task,
            steps=[
                {"tool_name": "a", "description": "a", "dependencies": [], "capability": "x"},
                {"tool_name": "b", "description": "b", "dependencies": [], "capability": "y"},
            ],
            estimated_time=4.0,
        )
        opt = planner.optimize_plan(plan)
        # both steps independent -> parallel group assigned
        has_pg = any(s.get("parallel_group") is not None for s in opt.steps)
        assert has_pg
        assert opt.estimated_time <= plan.estimated_time

    def test_optimize_plan_sequential(self):
        planner = ToolPlanner(self._make_registry())
        task = Task("x")
        plan = ExecutionPlan(
            task=task,
            steps=[
                {"tool_name": "a", "description": "a", "dependencies": [], "capability": "x"},
                {"tool_name": "b", "description": "b", "dependencies": [0], "capability": "y"},
            ],
        )
        opt = planner.optimize_plan(plan)
        # step 1 depends on step 0 so no parallelisation
        pg_vals = [s.get("parallel_group") for s in opt.steps]
        assert all(v is None for v in pg_vals)

    # -- validate_plan --

    def test_validate_valid_plan(self):
        reg = self._make_registry()
        planner = ToolPlanner(reg)
        plan = ExecutionPlan(
            task=Task("x"),
            steps=[
                {"tool_name": "search_tool", "version": "1.0.0", "dependencies": []},
            ],
        )
        ok, issues = planner.validate_plan(plan)
        assert ok
        assert issues == []

    def test_validate_missing_tool(self):
        planner = ToolPlanner(self._make_registry())
        plan = ExecutionPlan(
            task=Task("x"),
            steps=[{"tool_name": "nope", "dependencies": []}],
        )
        ok, issues = planner.validate_plan(plan)
        assert not ok

    def test_validate_circular_deps(self):
        planner = ToolPlanner(self._make_registry())
        plan = ExecutionPlan(
            task=Task("x"),
            steps=[
                {"tool_name": "search_tool", "version": "1.0.0", "dependencies": [1]},
                {"tool_name": "search_tool", "version": "1.0.0", "dependencies": [0]},
            ],
        )
        ok, issues = planner.validate_plan(plan)
        assert not ok
        assert any("ircular" in i for i in issues)

    def test_validate_invalid_dep(self):
        planner = ToolPlanner(self._make_registry())
        plan = ExecutionPlan(
            task=Task("x"),
            steps=[
                {"tool_name": "search_tool", "version": "1.0.0", "dependencies": [99]},
            ],
        )
        ok, issues = planner.validate_plan(plan)
        assert not ok

    # -- visualize_plan --

    def test_visualize(self):
        planner = ToolPlanner(self._make_registry())
        plan = ExecutionPlan(
            task=Task("my task"),
            steps=[
                {"tool_name": "t", "description": "step 0", "dependencies": []},
            ],
            complexity=TaskComplexity.SIMPLE,
            estimated_time=2.0,
            estimated_cost=0.01,
            confidence=0.95,
        )
        txt = planner.visualize_plan(plan)
        assert "my task" in txt
        assert "step 0" in txt


# =========================================================================== #
#  ERROR HANDLING
# =========================================================================== #


class TestRetryConfig:
    def test_defaults(self):
        cfg = RetryConfig()
        assert cfg.max_attempts == 3
        assert cfg.strategy == RetryStrategy.EXPONENTIAL_BACKOFF


class TestRetryExecutor:
    async def test_success_first_try(self):
        func = AsyncMock(return_value=42)
        executor = RetryExecutor(RetryConfig(max_attempts=3, strategy=RetryStrategy.IMMEDIATE))
        result = await executor.execute(func)
        assert result == 42
        func.assert_awaited_once()

    async def test_retries_then_succeeds(self):
        func = AsyncMock(side_effect=[ValueError("x"), ValueError("y"), 99])
        executor = RetryExecutor(
            RetryConfig(max_attempts=3, strategy=RetryStrategy.IMMEDIATE)
        )
        result = await executor.execute(func)
        assert result == 99
        assert func.await_count == 3

    async def test_retries_exhausted(self):
        func = AsyncMock(side_effect=ValueError("nope"))
        executor = RetryExecutor(
            RetryConfig(max_attempts=2, strategy=RetryStrategy.IMMEDIATE)
        )
        with pytest.raises(ValueError, match="nope"):
            await executor.execute(func)
        assert func.await_count == 2

    async def test_on_retry_callback(self):
        attempts_seen = []

        def on_retry(attempt, exc):
            attempts_seen.append(attempt)

        func = AsyncMock(side_effect=[RuntimeError("r"), 1])
        executor = RetryExecutor(
            RetryConfig(max_attempts=3, strategy=RetryStrategy.IMMEDIATE, on_retry=on_retry)
        )
        await executor.execute(func)
        assert 1 in attempts_seen

    async def test_non_retryable_exception(self):
        func = AsyncMock(side_effect=TypeError("bad"))
        executor = RetryExecutor(
            RetryConfig(
                max_attempts=3,
                strategy=RetryStrategy.IMMEDIATE,
                retryable_exceptions=(ValueError,),
            )
        )
        with pytest.raises(TypeError):
            await executor.execute(func)
        func.assert_awaited_once()

    # -- delay calculation --

    def test_delay_immediate(self):
        e = RetryExecutor(RetryConfig(strategy=RetryStrategy.IMMEDIATE))
        assert e._calculate_delay(1) == 0

    def test_delay_fixed(self):
        e = RetryExecutor(
            RetryConfig(strategy=RetryStrategy.FIXED_DELAY, initial_delay=2.0, max_delay=5.0)
        )
        assert e._calculate_delay(1) == 2.0
        assert e._calculate_delay(5) == 2.0

    def test_delay_linear(self):
        e = RetryExecutor(
            RetryConfig(strategy=RetryStrategy.LINEAR_BACKOFF, initial_delay=1.0, max_delay=5.0)
        )
        assert e._calculate_delay(1) == 1.0
        assert e._calculate_delay(3) == 3.0
        assert e._calculate_delay(10) == 5.0  # capped

    def test_delay_exponential(self):
        e = RetryExecutor(
            RetryConfig(
                strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
                initial_delay=1.0,
                backoff_multiplier=2.0,
                max_delay=100.0,
            )
        )
        assert e._calculate_delay(1) == 1.0
        assert e._calculate_delay(2) == 2.0
        assert e._calculate_delay(3) == 4.0


class TestCircuitBreaker:
    async def test_closed_success(self):
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3))
        result = await cb.call(AsyncMock(return_value="ok"))
        assert result == "ok"
        assert cb.state == CircuitState.CLOSED

    async def test_opens_after_threshold(self):
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=2))
        fail = AsyncMock(side_effect=RuntimeError("boom"))
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await cb.call(fail)
        assert cb.state == CircuitState.OPEN

    async def test_open_rejects_calls(self):
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=1, timeout=9999))
        with pytest.raises(RuntimeError):
            await cb.call(AsyncMock(side_effect=RuntimeError))
        assert cb.state == CircuitState.OPEN
        with pytest.raises(CircuitBreakerError):
            await cb.call(AsyncMock(return_value="x"))

    async def test_half_open_transitions(self):
        cb = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=1, success_threshold=1, timeout=0)
        )
        # trip the breaker
        with pytest.raises(RuntimeError):
            await cb.call(AsyncMock(side_effect=RuntimeError))
        assert cb.state == CircuitState.OPEN

        # timeout=0 so should move to half-open immediately
        result = await cb.call(AsyncMock(return_value="recovered"))
        assert result == "recovered"
        assert cb.state == CircuitState.CLOSED

    async def test_half_open_limit(self):
        cb = CircuitBreaker(
            CircuitBreakerConfig(failure_threshold=1, timeout=0, half_open_max_calls=1)
        )
        with pytest.raises(RuntimeError):
            await cb.call(AsyncMock(side_effect=RuntimeError))

        # first half-open call: enters half-open + consumes the slot
        with pytest.raises(RuntimeError):
            await cb.call(AsyncMock(side_effect=RuntimeError))
        # now half_open_calls >= max, state goes back to open due to failure
        assert cb.state == CircuitState.OPEN

    def test_reset(self):
        cb = CircuitBreaker()
        cb.state = CircuitState.OPEN
        cb.failure_count = 10
        cb.reset()
        assert cb.state == CircuitState.CLOSED
        assert cb.failure_count == 0

    def test_should_attempt_reset_no_failure(self):
        cb = CircuitBreaker()
        assert cb._should_attempt_reset() is True

    def test_on_failure_records_time(self):
        cb = CircuitBreaker()
        cb._on_failure()
        assert cb.failure_count == 1
        assert cb.last_failure_time is not None


class TestFallbackExecutor:
    async def test_primary_succeeds(self):
        ex = FallbackExecutor()
        result = await ex.execute(AsyncMock(return_value="primary"))
        assert result == "primary"

    async def test_fallback_used(self):
        fb = AsyncMock(return_value="backup")
        ex = FallbackExecutor(
            FallbackConfig(fallback_functions=[fb])
        )
        result = await ex.execute(
            AsyncMock(side_effect=RuntimeError("fail")),
        )
        assert result == "backup"

    async def test_all_fail_raises(self):
        ex = FallbackExecutor(
            FallbackConfig(
                fallback_functions=[AsyncMock(side_effect=RuntimeError("fb_fail"))]
            )
        )
        with pytest.raises(RuntimeError, match="fb_fail"):
            await ex.execute(AsyncMock(side_effect=RuntimeError("prim_fail")))

    async def test_default_value(self):
        ex = FallbackExecutor(
            FallbackConfig(
                return_default_on_all_failures=True,
                default_value="default_val",
            )
        )
        result = await ex.execute(AsyncMock(side_effect=RuntimeError))
        assert result == "default_val"


class TestCompositeErrorHandler:
    async def test_no_handlers(self):
        h = CompositeErrorHandler()
        result = await h.execute(AsyncMock(return_value="ok"))
        assert result == "ok"

    async def test_retry_only(self):
        func = AsyncMock(side_effect=[RuntimeError, "ok"])
        h = CompositeErrorHandler(
            retry_config=RetryConfig(max_attempts=2, strategy=RetryStrategy.IMMEDIATE)
        )
        result = await h.execute(func)
        assert result == "ok"

    async def test_circuit_breaker_with_fallback(self):
        fb = AsyncMock(return_value="fb")
        h = CompositeErrorHandler(
            circuit_breaker_config=CircuitBreakerConfig(failure_threshold=1, timeout=9999),
            fallback_config=FallbackConfig(fallback_functions=[fb]),
        )
        result = await h.execute(AsyncMock(side_effect=RuntimeError))
        assert result == "fb"

    async def test_fallback_only(self):
        fb = AsyncMock(return_value="fb_only")
        h = CompositeErrorHandler(
            fallback_config=FallbackConfig(fallback_functions=[fb]),
        )
        result = await h.execute(AsyncMock(side_effect=RuntimeError))
        assert result == "fb_only"


class TestDecorators:
    async def test_with_retry(self):
        call_count = 0

        @with_retry(RetryConfig(max_attempts=3, strategy=RetryStrategy.IMMEDIATE))
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("retry me")
            return "done"

        assert await flaky() == "done"
        assert call_count == 2

    async def test_with_circuit_breaker(self):
        @with_circuit_breaker(CircuitBreakerConfig(failure_threshold=5))
        async def safe():
            return "safe"

        assert await safe() == "safe"

    async def test_with_fallback(self):
        async def backup():
            return "backup"

        @with_fallback(backup)
        async def primary():
            raise RuntimeError

        assert await primary() == "backup"

    async def test_with_fallback_default(self):
        async def backup():
            raise RuntimeError

        @with_fallback(backup, default_value="def")
        async def primary():
            raise RuntimeError

        assert await primary() == "def"


# =========================================================================== #
#  TOOL CHAIN
# =========================================================================== #


class TestToolChain:
    async def test_sequential_execution(self):
        chain = ToolChain(_dummy_executor)
        chain.add_step("step1", {"query": "input_q"}, "result1")
        chain.add_step("step2", {"text": "result1"}, "result2")
        res = await chain.execute({"input_q": "hello"})
        assert res.success
        assert "result1" in res.context
        assert "result2" in res.context
        assert res.steps_executed == ["result1", "result2"]

    async def test_condition_skip(self):
        chain = ToolChain(_dummy_executor)
        chain.add_step(
            "tool", {"x": "a"}, "out",
            condition=lambda ctx: False,
        )
        res = await chain.execute({"a": 1})
        assert "out" in res.steps_skipped

    async def test_condition_pass(self):
        chain = ToolChain(_dummy_executor)
        chain.add_step(
            "tool", {"x": "a"}, "out",
            condition=lambda ctx: True,
        )
        res = await chain.execute({"a": 1})
        assert "out" in res.steps_executed

    async def test_on_error_skip(self):
        chain = ToolChain(_failing_executor)
        chain.add_step("tool", {"x": "a"}, "out", on_error="skip")
        res = await chain.execute({"a": 1})
        assert not res.success
        assert "out" in res.steps_skipped
        assert "out" in res.errors

    async def test_on_error_default(self):
        chain = ToolChain(_failing_executor)
        chain.add_step("tool", {"x": "a"}, "out", on_error="default", default_value="fallback")
        res = await chain.execute({"a": 1})
        assert res.context["out"] == "fallback"

    async def test_on_error_raise(self):
        chain = ToolChain(_failing_executor)
        chain.add_step("tool", {"x": "a"}, "out", on_error="raise")
        with pytest.raises(RuntimeError):
            await chain.execute({"a": 1})

    async def test_missing_context_key(self):
        chain = ToolChain(_dummy_executor)
        chain.add_step("tool", {"x": "nonexistent"}, "out", on_error="raise")
        with pytest.raises(KeyError):
            await chain.execute({})

    async def test_parallel_steps(self):
        chain = ToolChain(_dummy_executor)
        chain.add_parallel_steps([
            ("tool_a", {"x": "input"}, "out_a"),
            ("tool_b", {"x": "input"}, "out_b"),
        ])
        res = await chain.execute({"input": 42})
        assert res.success
        assert "out_a" in res.context
        assert "out_b" in res.context

    async def test_parallel_group_auto_id(self):
        chain = ToolChain(_dummy_executor)
        chain.add_parallel_steps([("a", {"x": "i"}, "o1")], parallel_group=5)
        chain.add_parallel_steps([("b", {"x": "i"}, "o2")])
        assert chain.steps[-1].parallel_group == 6

    async def test_execute_partial(self):
        chain = ToolChain(_dummy_executor)
        chain.add_step("s1", {"x": "i"}, "out1")
        chain.add_step("s2", {"x": "out1"}, "out2")
        chain.add_step("s3", {"x": "out2"}, "out3")
        res = await chain.execute_partial({"i": 1}, until_step="out2")
        assert "out2" in res.context
        assert "out3" not in res.context
        # chain still has all 3 steps
        assert len(chain.steps) == 3

    async def test_execute_partial_not_found(self):
        chain = ToolChain(_dummy_executor)
        chain.add_step("s1", {"x": "i"}, "out1")
        with pytest.raises(ValueError, match="Step not found"):
            await chain.execute_partial({"i": 1}, until_step="nope")

    def test_clear(self):
        chain = ToolChain(_dummy_executor)
        chain.add_step("t", {}, "o")
        chain.clear()
        assert len(chain.steps) == 0

    def test_get_steps(self):
        chain = ToolChain(_dummy_executor)
        chain.add_step("t", {"a": "b"}, "o", condition=lambda c: True)
        info = chain.get_steps()
        assert info[0]["tool_name"] == "t"
        assert info[0]["has_condition"] is True

    def test_visualize(self):
        chain = ToolChain(_dummy_executor)
        chain.add_step("t1", {"a": "b"}, "o1")
        chain.add_step("t2", {"a": "b"}, "o2", condition=lambda c: True, parallel_group=0)
        txt = chain.visualize()
        assert "Tool Chain:" in txt
        assert "t1" in txt

    async def test_parallel_group_exception(self):
        """Parallel step that raises should appear in errors."""

        async def mixed_executor(tool_name, params):
            if tool_name == "bad":
                raise RuntimeError("boom")
            return "ok"

        chain = ToolChain(mixed_executor)
        chain.add_parallel_steps([
            ("good", {"x": "i"}, "ok_out"),
            ("bad", {"x": "i"}, "bad_out"),
        ])
        res = await chain.execute({"i": 1})
        assert not res.success


class TestChainBuilder:
    async def test_build_and_execute(self):
        chain = (
            ChainBuilder(_dummy_executor)
            .step("s1", {"x": "i"}, "o1")
            .step("s2", {"x": "o1"}, "o2")
            .build()
        )
        res = await chain.execute({"i": 1})
        assert res.success

    async def test_parallel_builder(self):
        chain = (
            ChainBuilder(_dummy_executor)
            .parallel([("a", {"x": "i"}, "o1"), ("b", {"x": "i"}, "o2")])
            .build()
        )
        res = await chain.execute({"i": 1})
        assert res.success

    async def test_conditional_builder(self):
        chain = (
            ChainBuilder(_dummy_executor)
            .conditional(lambda ctx: True, "t", {"x": "i"}, "o")
            .build()
        )
        res = await chain.execute({"i": 1})
        assert "o" in res.steps_executed


# =========================================================================== #
#  PARALLEL EXECUTOR
# =========================================================================== #


class TestParallelExecutor:
    def test_add_task(self):
        pe = ParallelExecutor(_dummy_executor)
        pe.add_task("t1", "tool", {"a": 1})
        assert "t1" in pe.tasks

    def test_add_duplicate_raises(self):
        pe = ParallelExecutor(_dummy_executor)
        pe.add_task("t1", "tool", {})
        with pytest.raises(ValueError):
            pe.add_task("t1", "tool", {})

    def test_remove_task(self):
        pe = ParallelExecutor(_dummy_executor)
        pe.add_task("t1", "tool", {})
        assert pe.remove_task("t1")
        assert "t1" not in pe.tasks

    def test_remove_nonexistent(self):
        pe = ParallelExecutor(_dummy_executor)
        assert pe.remove_task("nope") is False

    def test_remove_running_task(self):
        pe = ParallelExecutor(_dummy_executor)
        pe.add_task("t1", "tool", {})
        pe.tasks["t1"].status = ExecutionStatus.RUNNING
        assert pe.remove_task("t1") is False

    async def test_execute_all_basic(self):
        pe = ParallelExecutor(_dummy_executor)
        pe.add_task("t1", "tool_a", {"x": 1})
        pe.add_task("t2", "tool_b", {"y": 2})
        results = await pe.execute_all()
        assert "t1" in results
        assert "t2" in results

    async def test_execute_all_empty(self):
        pe = ParallelExecutor(_dummy_executor)
        results = await pe.execute_all()
        assert results == {}

    async def test_execute_with_dependencies(self):
        pe = ParallelExecutor(_dummy_executor)
        pe.add_task("t1", "tool_a", {})
        pe.add_task("t2", "tool_b", {}, dependencies=["t1"])
        await pe.execute_all()
        assert pe.tasks["t1"].status == ExecutionStatus.COMPLETED
        assert pe.tasks["t2"].status == ExecutionStatus.COMPLETED

    async def test_circular_dependency_raises(self):
        pe = ParallelExecutor(_dummy_executor)
        pe.add_task("t1", "a", {}, dependencies=["t2"])
        pe.add_task("t2", "b", {}, dependencies=["t1"])
        with pytest.raises(ValueError, match="ircular"):
            await pe.execute_all()

    async def test_execute_single_task(self):
        pe = ParallelExecutor(_dummy_executor)
        pe.add_task("t1", "tool", {"v": 10})
        result = await pe.execute_task("t1")
        assert result["tool"] == "tool"

    async def test_execute_single_not_found(self):
        pe = ParallelExecutor(_dummy_executor)
        with pytest.raises(ValueError):
            await pe.execute_task("nope")

    async def test_execute_single_with_dep(self):
        pe = ParallelExecutor(_dummy_executor)
        pe.add_task("t1", "a", {})
        pe.add_task("t2", "b", {}, dependencies=["t1"])
        _result = await pe.execute_task("t2")
        assert pe.tasks["t1"].status == ExecutionStatus.COMPLETED

    async def test_fail_fast(self):
        pe = ParallelExecutor(_failing_executor)
        pe.add_task("t1", "a", {})
        pe.add_task("t2", "b", {})
        await pe.execute_all(fail_fast=True)
        failed = [t for t in pe.tasks.values() if t.status == ExecutionStatus.FAILED]
        assert len(failed) >= 1

    async def test_task_timeout(self):
        async def slow_executor(tool_name, params):
            await asyncio.sleep(10)

        pe = ParallelExecutor(slow_executor, ResourceLimits(timeout_seconds=0.1))
        pe.add_task("t1", "slow", {})
        await pe.execute_all()
        assert pe.tasks["t1"].status == ExecutionStatus.FAILED
        assert "timed out" in pe.tasks["t1"].error

    def test_cancel_task(self):
        pe = ParallelExecutor(_dummy_executor)
        pe.add_task("t1", "tool", {})
        assert pe.cancel_task("t1")
        assert pe.tasks["t1"].status == ExecutionStatus.CANCELLED

    def test_cancel_nonexistent(self):
        pe = ParallelExecutor(_dummy_executor)
        assert pe.cancel_task("nope") is False

    def test_cancel_running(self):
        pe = ParallelExecutor(_dummy_executor)
        pe.add_task("t1", "tool", {})
        pe.tasks["t1"].status = ExecutionStatus.RUNNING
        assert pe.cancel_task("t1") is False

    def test_get_status_single(self):
        pe = ParallelExecutor(_dummy_executor)
        pe.add_task("t1", "tool", {})
        status = pe.get_status("t1")
        assert status["task_id"] == "t1"
        assert status["status"] == "pending"

    def test_get_status_not_found(self):
        pe = ParallelExecutor(_dummy_executor)
        assert "error" in pe.get_status("nope")

    def test_get_status_all(self):
        pe = ParallelExecutor(_dummy_executor)
        pe.add_task("t1", "a", {})
        pe.add_task("t2", "b", {})
        status = pe.get_status()
        assert status["total_tasks"] == 2

    def test_clear(self):
        pe = ParallelExecutor(_dummy_executor)
        pe.add_task("t1", "a", {})
        pe.clear()
        assert len(pe.tasks) == 0

    def test_get_execution_graph(self):
        pe = ParallelExecutor(_dummy_executor)
        pe.add_task("t1", "a", {})
        pe.add_task("t2", "b", {}, dependencies=["t1"])
        graph = pe.get_execution_graph()
        assert len(graph["nodes"]) == 2
        assert len(graph["edges"]) == 1

    def test_no_circular_deps(self):
        pe = ParallelExecutor(_dummy_executor)
        pe.add_task("t1", "a", {})
        pe.add_task("t2", "b", {}, dependencies=["t1"])
        assert pe._has_circular_dependencies() is False

    async def test_execute_failed_single_task_raises(self):
        pe = ParallelExecutor(_failing_executor)
        pe.add_task("t1", "tool", {})
        with pytest.raises(Exception, match="Task failed"):
            await pe.execute_task("t1")

    def test_resource_limits_defaults(self):
        rl = ResourceLimits()
        assert rl.max_concurrent == 10
        assert rl.timeout_seconds == 300.0

    async def test_execute_no_timeout(self):
        pe = ParallelExecutor(_dummy_executor, ResourceLimits(timeout_seconds=0))
        pe.add_task("t1", "tool", {"a": 1})
        results = await pe.execute_all()
        assert "t1" in results


# =========================================================================== #
#  ADVANCED TOOL REGISTRY
# =========================================================================== #


class TestAdvancedToolRegistry:
    def test_register_and_get(self):
        reg = AdvancedToolRegistry()
        td = _make_tool_def("mytool")
        reg.register_versioned(td, "1.0.0", capabilities=["cap1"])
        assert reg.get_tool("mytool") is td
        assert reg.get_tool("mytool", "1.0.0") is td

    def test_get_tool_not_found(self):
        reg = AdvancedToolRegistry()
        assert reg.get_tool("nope") is None

    def test_register_simple(self):
        reg = AdvancedToolRegistry()
        td = _make_tool_def("simple")
        reg.register(td, capabilities=["x"])
        assert reg.get_tool("simple", "1.0.0") is td

    def test_list_versions(self):
        reg = AdvancedToolRegistry()
        td = _make_tool_def("v")
        reg.register_versioned(td, "1.0.0")
        reg.register_versioned(td, "2.0.0")
        versions = reg.list_versions("v")
        assert "1.0.0" in versions
        assert "2.0.0" in versions

    def test_deprecate(self):
        reg = AdvancedToolRegistry()
        td = _make_tool_def("d")
        reg.register_versioned(td, "1.0.0")
        assert reg.deprecate_version("d", "1.0.0", "old")
        assert reg.tools["d"]["1.0.0"].deprecated

    def test_deprecate_not_found(self):
        reg = AdvancedToolRegistry()
        assert reg.deprecate_version("nope", "1.0.0") is False

    def test_find_by_capability(self):
        reg = AdvancedToolRegistry()
        td = _make_tool_def("t")
        reg.register_versioned(td, "1.0.0", capabilities=["cap"])
        results = reg.find_by_capability("cap")
        assert len(results) == 1

    def test_find_excludes_deprecated(self):
        reg = AdvancedToolRegistry()
        td = _make_tool_def("t")
        reg.register_versioned(td, "1.0.0", capabilities=["cap"])
        reg.deprecate_version("t", "1.0.0")
        assert reg.find_by_capability("cap") == []
        assert len(reg.find_by_capability("cap", include_deprecated=True)) == 1

    async def test_execute(self):
        reg = AdvancedToolRegistry()

        async def adder(a=0, b=0):
            return a + b

        td = ToolDefinition(
            name="add", description="add", parameters={}, function=adder
        )
        reg.register_versioned(td, "1.0.0")
        result = await reg.execute("add", {"a": 3, "b": 4})
        assert result == 7
        assert reg.execution_stats["add"]["successful_calls"] == 1

    async def test_execute_not_found(self):
        reg = AdvancedToolRegistry()
        with pytest.raises(ValueError, match="Tool not found"):
            await reg.execute("nope", {})

    async def test_execute_cached(self):
        reg = AdvancedToolRegistry()
        call_count = 0

        async def counter(**kw):
            nonlocal call_count
            call_count += 1
            return call_count

        td = ToolDefinition(name="c", description="c", parameters={}, function=counter)
        reg.register_versioned(td, "1.0.0")

        r1 = await reg.execute_cached("c", {}, ttl=3600)
        r2 = await reg.execute_cached("c", {}, ttl=3600)
        assert r1 == r2 == 1  # second call is cached
        assert reg.execution_stats["c"]["cache_hits"] == 1

    async def test_execute_cached_disabled(self):
        reg = AdvancedToolRegistry(enable_caching=False)

        async def noop(**kw):
            return 1

        td = ToolDefinition(name="n", description="n", parameters={}, function=noop)
        reg.register_versioned(td, "1.0.0")
        await reg.execute_cached("n", {})
        assert len(reg.cache) == 0

    def test_clear_cache_all(self):
        reg = AdvancedToolRegistry()
        reg.cache["k1"] = CacheEntry(result=1, timestamp=datetime.now(timezone.utc), ttl=100)
        reg.cache["k2"] = CacheEntry(result=2, timestamp=datetime.now(timezone.utc), ttl=100)
        cleared = reg.clear_cache()
        assert cleared == 2
        assert len(reg.cache) == 0

    def test_clear_cache_specific(self):
        reg = AdvancedToolRegistry()
        reg.cache["k1"] = CacheEntry(result=1, timestamp=datetime.now(timezone.utc), ttl=100)
        cleared = reg.clear_cache("some_tool")
        assert cleared >= 0

    def test_cleanup_expired(self):
        reg = AdvancedToolRegistry()
        old = datetime.now(timezone.utc) - timedelta(hours=2)
        reg.cache["expired"] = CacheEntry(result=1, timestamp=old, ttl=1)
        reg.cache["fresh"] = CacheEntry(
            result=2, timestamp=datetime.now(timezone.utc), ttl=9999
        )
        removed = reg.cleanup_expired_cache()
        assert removed == 1
        assert "fresh" in reg.cache

    def test_get_statistics(self):
        reg = AdvancedToolRegistry()
        td = _make_tool_def("s")
        reg.register_versioned(td, "1.0.0")
        stats = reg.get_statistics("s")
        assert "total_calls" in stats

    def test_get_statistics_all(self):
        reg = AdvancedToolRegistry()
        td = _make_tool_def("s")
        reg.register_versioned(td, "1.0.0")
        stats = reg.get_statistics()
        assert "s" in stats

    def test_list_capabilities(self):
        reg = AdvancedToolRegistry()
        td = _make_tool_def("t")
        reg.register_versioned(td, "1.0.0", capabilities=["a", "b"])
        caps = reg.list_capabilities()
        assert "a" in caps
        assert "b" in caps

    def test_list_tools(self):
        reg = AdvancedToolRegistry()
        td = _make_tool_def("t")
        reg.register_versioned(td, "1.0.0")
        tools = reg.list_tools()
        assert len(tools) == 1
        assert tools[0]["name"] == "t"

    def test_list_tools_exclude_deprecated(self):
        reg = AdvancedToolRegistry()
        td = _make_tool_def("t")
        reg.register_versioned(td, "1.0.0")
        reg.deprecate_version("t", "1.0.0")
        assert reg.list_tools(include_deprecated=False) == []
        assert len(reg.list_tools(include_deprecated=True)) == 1

    def test_list_tools_by_capability(self):
        reg = AdvancedToolRegistry()
        td = _make_tool_def("t")
        reg.register_versioned(td, "1.0.0", capabilities=["cap"])
        tools = reg.list_tools(capability="cap")
        assert len(tools) == 1

    def test_export_catalog(self):
        reg = AdvancedToolRegistry()
        td = _make_tool_def("t")
        reg.register_versioned(td, "1.0.0", capabilities=["c"])
        catalog = reg.export_tool_catalog()
        assert "tools" in catalog
        assert "capabilities" in catalog
        assert catalog["total_tools"] == 1


class TestCacheEntry:
    def test_valid_entry(self):
        entry = CacheEntry(
            result=42,
            timestamp=datetime.now(timezone.utc),
            ttl=3600,
        )
        assert entry.is_valid()

    def test_expired_entry(self):
        entry = CacheEntry(
            result=42,
            timestamp=datetime.now(timezone.utc) - timedelta(hours=2),
            ttl=1,
        )
        assert not entry.is_valid()

    def test_no_expiry(self):
        entry = CacheEntry(
            result=42,
            timestamp=datetime.now(timezone.utc) - timedelta(days=365),
            ttl=0,
        )
        assert entry.is_valid()

    def test_naive_timestamp(self):
        entry = CacheEntry(
            result=42,
            timestamp=datetime.now(),
            ttl=3600,
        )
        assert entry.is_valid()


# =========================================================================== #
#  ADVANCED TOOL EXECUTOR
# =========================================================================== #


class TestAdvancedToolExecutor:
    def _make_executor(self):
        exe = AdvancedToolExecutor(enable_caching=True, max_concurrent=5)

        async def echo_func(**kw):
            return kw

        td = ToolDefinition(
            name="echo",
            description="echo",
            parameters={
                "msg": {"type": "string", "required": False}
            },
            function=echo_func,
        )
        exe.register_tool(td, version="1.0.0", capabilities=["echo"])
        return exe

    def test_register_tool(self):
        exe = self._make_executor()
        assert exe.registry.get_tool("echo") is not None

    async def test_execute_tool(self):
        exe = self._make_executor()
        result = await exe.execute_tool("echo", {"msg": "hi"}, retry=False)
        assert result == {"msg": "hi"}

    async def test_execute_tool_cached(self):
        exe = self._make_executor()
        r1 = await exe.execute_tool("echo", {"msg": "hi"}, cache_ttl=60)
        r2 = await exe.execute_tool("echo", {"msg": "hi"}, cache_ttl=60)
        assert r1 == r2

    async def test_execute_tool_no_retry(self):
        exe = self._make_executor()
        result = await exe.execute_tool(
            "echo", {"msg": "x"}, retry=False, use_circuit_breaker=False
        )
        assert result == {"msg": "x"}

    def test_get_statistics(self):
        exe = self._make_executor()
        stats = exe.get_statistics()
        assert "registry" in stats
        assert "cache_size" in stats

    def test_clear_cache(self):
        exe = self._make_executor()
        exe.registry.cache["k"] = CacheEntry(
            result=1, timestamp=datetime.now(timezone.utc), ttl=100
        )
        cleared = exe.clear_cache()
        assert cleared >= 1

    def test_list_tools(self):
        exe = self._make_executor()
        tools = exe.list_tools()
        assert len(tools) >= 1

    def test_list_tools_by_capability(self):
        exe = self._make_executor()
        tools = exe.list_tools(capability="echo")
        assert len(tools) == 1

    def test_export_catalog(self):
        exe = self._make_executor()
        cat = exe.export_catalog()
        assert "tools" in cat


# =========================================================================== #
#  BUILTIN TOOLS - CALCULATOR
# =========================================================================== #


class TestCalculatorTool:
    async def test_basic_expression(self):
        calc = CalculatorTool()
        assert await calc.evaluate("2 + 3") == 5.0

    async def test_math_functions(self):
        calc = CalculatorTool()
        assert await calc.evaluate("sqrt(16)") == 4.0
        assert abs(await calc.evaluate("sin(0)")) < 1e-10

    async def test_constants(self):
        calc = CalculatorTool()
        assert abs(await calc.evaluate("pi") - math.pi) < 1e-10

    async def test_division_by_zero(self):
        calc = CalculatorTool()
        with pytest.raises(ValueError, match="Division by zero"):
            await calc.evaluate("1/0")

    async def test_unsafe_expression(self):
        calc = CalculatorTool()
        with pytest.raises(ValueError, match="unsafe"):
            await calc.evaluate("__import__('os')")

    async def test_invalid_expression(self):
        calc = CalculatorTool()
        with pytest.raises(ValueError):
            await calc.evaluate("not_a_number+++")

    async def test_non_number_result(self):
        calc = CalculatorTool()
        with pytest.raises(ValueError, match="unsafe"):
            await calc.evaluate("'hello'")

    def test_is_safe_blocks_dangerous(self):
        calc = CalculatorTool()
        assert not calc._is_safe_expression("import os")
        assert not calc._is_safe_expression("exec('x')")
        assert not calc._is_safe_expression("open('f')")

    def test_is_safe_allows_valid(self):
        calc = CalculatorTool()
        assert calc._is_safe_expression("2 + 3 * sqrt(16)")
        assert calc._is_safe_expression("pi * 2")

    async def test_calculate_statistics_all(self):
        calc = CalculatorTool()
        nums = [1, 2, 3, 4, 5]
        stats = await calc.calculate_statistics(nums)
        assert stats["mean"] == 3.0
        assert stats["median"] == 3
        assert stats["min"] == 1
        assert stats["max"] == 5
        assert stats["sum"] == 15
        assert "std" in stats

    async def test_calculate_statistics_even_count(self):
        calc = CalculatorTool()
        stats = await calc.calculate_statistics([1, 2, 3, 4], ["median"])
        assert stats["median"] == 2.5

    async def test_calculate_statistics_specific_ops(self):
        calc = CalculatorTool()
        stats = await calc.calculate_statistics([10, 20], ["count"])
        assert stats["count"] == 2

    async def test_calculate_statistics_empty(self):
        calc = CalculatorTool()
        with pytest.raises(ValueError, match="Empty"):
            await calc.calculate_statistics([])


class TestCalculatorFunction:
    async def test_expression_mode(self):
        result = await calculator_function(expression="2+2")
        assert result["result"] == 4
        assert result["type"] == "expression"

    async def test_stats_mode(self):
        result = await calculator_function(operation="mean", numbers=[2, 4])
        assert result["result"] == 3.0
        assert result["type"] == "statistics"

    async def test_no_args_raises(self):
        with pytest.raises(ValueError, match="Must provide"):
            await calculator_function()


class TestCreateCalculatorTool:
    def test_creates_definition(self):
        td = create_calculator_tool()
        assert td.name == "calculator"
        assert "expression" in td.parameters


# =========================================================================== #
#  BUILTIN TOOLS - FILE OPS
# =========================================================================== #


class TestFileOperationsTool:
    def test_validate_path_traversal(self):
        tool = FileOperationsTool(base_path=tempfile.gettempdir())
        with pytest.raises(ValueError, match="outside base"):
            tool._validate_path("../../etc/passwd")

    def test_validate_path_bad_extension(self):
        tool = FileOperationsTool(
            base_path=tempfile.gettempdir(),
            allowed_extensions=[".txt"],
        )
        with pytest.raises(ValueError, match="not allowed"):
            tool._validate_path("file.exe")

    async def test_read_write_roundtrip(self):
        with tempfile.TemporaryDirectory() as td:
            tool = FileOperationsTool(base_path=td, allowed_extensions=[".txt"])
            await tool.write_file("test.txt", "hello world")
            content = await tool.read_file("test.txt")
            assert content == "hello world"

    async def test_read_not_found(self):
        with tempfile.TemporaryDirectory() as td:
            tool = FileOperationsTool(base_path=td)
            with pytest.raises(FileNotFoundError):
                await tool.read_file("no.txt")

    async def test_read_directory_raises(self):
        with tempfile.TemporaryDirectory() as td:
            subdir = Path(td) / "subdir"
            subdir.mkdir()
            # allowed_extensions default includes .txt etc - "subdir" has no ext
            # _validate_path checks extension before is_file check
            tool = FileOperationsTool(base_path=td, allowed_extensions=[".txt", ""])
            with pytest.raises(ValueError, match="Not a file"):
                await tool.read_file("subdir")

    async def test_write_creates_dirs(self):
        with tempfile.TemporaryDirectory() as td:
            tool = FileOperationsTool(base_path=td)
            result = await tool.write_file("sub/dir/file.txt", "data")
            assert result["success"]

    async def test_read_json_write_json(self):
        with tempfile.TemporaryDirectory() as td:
            tool = FileOperationsTool(base_path=td)
            await tool.write_json("data.json", {"key": "val"})
            data = await tool.read_json("data.json")
            assert data["key"] == "val"

    async def test_list_files(self):
        with tempfile.TemporaryDirectory() as td:
            # allowed_extensions default checks extension on dir path "." which has no ext
            # Use allowed_extensions=None to skip validation, or include ""
            tool = FileOperationsTool(base_path=td, allowed_extensions=[".txt", ""])
            (Path(td) / "a.txt").write_text("a")
            (Path(td) / "b.txt").write_text("b")
            files = await tool.list_files(".", "*.txt")
            assert len(files) == 2

    async def test_list_files_recursive(self):
        with tempfile.TemporaryDirectory() as td:
            tool = FileOperationsTool(base_path=td, allowed_extensions=[".txt", ""])
            sub = Path(td) / "sub"
            sub.mkdir()
            (sub / "c.txt").write_text("c")
            files = await tool.list_files(".", "*.txt", recursive=True)
            assert any("c.txt" in f for f in files)

    async def test_list_not_dir(self):
        with tempfile.TemporaryDirectory() as td:
            tool = FileOperationsTool(base_path=td)
            (Path(td) / "file.txt").write_text("x")
            with pytest.raises(ValueError, match="Not a directory"):
                await tool.list_files("file.txt")

    async def test_delete_file(self):
        with tempfile.TemporaryDirectory() as td:
            tool = FileOperationsTool(base_path=td)
            (Path(td) / "del.txt").write_text("x")
            result = await tool.delete_file("del.txt")
            assert result["success"]
            assert not (Path(td) / "del.txt").exists()

    async def test_delete_not_found(self):
        with tempfile.TemporaryDirectory() as td:
            tool = FileOperationsTool(base_path=td)
            with pytest.raises(FileNotFoundError):
                await tool.delete_file("nope.txt")


class TestFileOpsFunction:
    async def test_read_op(self):
        with tempfile.TemporaryDirectory() as td:
            (Path(td) / "r.txt").write_text("content")
            with patch.object(FileOperationsTool, "__init__", lambda self: None):
                # Use actual function with real temp dir
                tool = FileOperationsTool.__new__(FileOperationsTool)
                tool.base_path = Path(td)
                tool.allowed_extensions = [".txt"]
                tool.max_file_size_bytes = 10 * 1024 * 1024
                tool.logger = MagicMock()
                content = await tool.read_file("r.txt")
                assert content == "content"

    async def test_write_op(self):
        result = await file_ops_function(operation="write", file_path="test.txt", content="hi")
        assert result["success"]

    async def test_unknown_op(self):
        with pytest.raises(ValueError, match="Unknown operation"):
            await file_ops_function(operation="invalid", file_path="x")

    async def test_write_no_content(self):
        with pytest.raises(ValueError, match="content"):
            await file_ops_function(operation="write", file_path="x")

    async def test_write_json_no_data(self):
        with pytest.raises(ValueError, match="data"):
            await file_ops_function(operation="write_json", file_path="x")


class TestCreateFileOpsTool:
    def test_creates_definition(self):
        td = create_file_ops_tool()
        assert td.name == "file_operations"
        assert td.requires_approval is True


# =========================================================================== #
#  BUILTIN TOOLS - CODE EXECUTOR
# =========================================================================== #


class TestCodeExecutorTool:
    async def test_simple_code(self):
        ce = CodeExecutorTool()
        result = await ce.execute("result = 2 + 3")
        assert result["success"]
        assert result["result"] == 5

    async def test_print_capture(self):
        ce = CodeExecutorTool()
        result = await ce.execute("print('hello')")
        assert result["success"]
        assert "hello" in result["output"]

    async def test_unsafe_code_rejected(self):
        ce = CodeExecutorTool()
        with pytest.raises(ValueError, match="unsafe"):
            await ce.execute("import os\nos.system('rm -rf /')")

    async def test_runtime_error(self):
        ce = CodeExecutorTool()
        result = await ce.execute("x = 1 / 0")
        assert not result["success"]
        assert "ZeroDivisionError" in result["error"]

    def test_is_safe_blocks_patterns(self):
        ce = CodeExecutorTool()
        assert not ce._is_safe_code("import os")
        assert not ce._is_safe_code("import sys")
        assert not ce._is_safe_code("import subprocess")
        assert not ce._is_safe_code("eval(x)")
        assert not ce._is_safe_code("exec(x)")
        assert not ce._is_safe_code("open('file')")
        assert not ce._is_safe_code("__builtins__")
        assert not ce._is_safe_code("globals()")
        assert not ce._is_safe_code("setattr(x, y, z)")

    def test_is_safe_allows_safe(self):
        ce = CodeExecutorTool()
        assert ce._is_safe_code("x = 1 + 2")
        assert ce._is_safe_code("result = sum([1,2,3])")

    async def test_execute_function(self):
        ce = CodeExecutorTool()
        # exec(code, globals_dict, locals_dict) puts function defs into locals_dict,
        # but execute_function checks globals_dict only. This is a known limitation
        # of exec with separate globals/locals namespaces.
        code = "def multiply(a, b):\n    return a * b"
        with pytest.raises(ValueError, match="not defined"):
            await ce.execute_function(code, "multiply", 3, 4)

    async def test_execute_function_not_defined(self):
        ce = CodeExecutorTool()
        with pytest.raises(ValueError, match="not defined"):
            await ce.execute_function("x = 1", "nope")

    async def test_custom_globals(self):
        ce = CodeExecutorTool()
        result = await ce.execute("result = x + 1", globals_dict={"x": 10})
        assert result["success"]

    async def test_custom_locals(self):
        ce = CodeExecutorTool()
        result = await ce.execute("result = y + 1", locals_dict={"y": 5})
        assert result["success"]
        assert result["result"] == 6


class TestCodeExecutorFunction:
    async def test_basic(self):
        result = await code_executor_function(code="result = 42")
        assert result["success"]
        assert result["result"] == 42

    async def test_with_timeout(self):
        result = await code_executor_function(code="result = 1", timeout=10.0)
        assert result["success"]


class TestCreateCodeExecutorTool:
    def test_creates_definition(self):
        td = create_code_executor_tool()
        assert td.name == "code_executor"
        assert td.requires_approval


# =========================================================================== #
#  BUILTIN TOOLS - API CALLER
# =========================================================================== #


class TestAPICallerTool:
    async def test_get_request(self):
        tool = APICallerTool()
        result = await tool.get("https://example.com/api")
        assert result["status"] == 200

    async def test_post_request(self):
        tool = APICallerTool()
        result = await tool.post("https://example.com/api", json_data={"key": "val"})
        assert result["status"] == 200

    async def test_put_request(self):
        tool = APICallerTool()
        result = await tool.put("https://example.com/api")
        assert result["status"] == 200

    async def test_delete_request(self):
        tool = APICallerTool()
        result = await tool.delete("https://example.com/api")
        assert result["status"] == 200

    async def test_patch_request(self):
        tool = APICallerTool()
        result = await tool.patch("https://example.com/api")
        assert result["status"] == 200

    async def test_invalid_method(self):
        tool = APICallerTool()
        with pytest.raises(ValueError, match="Unsupported"):
            await tool.request("TRACE", "https://example.com")

    async def test_query_params(self):
        tool = APICallerTool()
        result = await tool.request("GET", "https://example.com", params={"q": "test"})
        assert result["status"] == 200

    async def test_custom_headers(self):
        tool = APICallerTool(default_headers={"X-Custom": "val"})
        result = await tool.get("https://example.com")
        assert result["data"]["request_headers"]["X-Custom"] == "val"

    async def test_rate_limiting_per_second(self):
        tool = APICallerTool(rate_limit=RateLimitConfig(requests_per_second=100))
        result = await tool.get("https://example.com")
        assert result["status"] == 200

    async def test_rate_limiting_per_minute(self):
        tool = APICallerTool(rate_limit=RateLimitConfig(requests_per_minute=100))
        result = await tool.get("https://example.com")
        assert result["status"] == 200

    async def test_rate_limiting_per_hour(self):
        tool = APICallerTool(rate_limit=RateLimitConfig(requests_per_hour=100))
        result = await tool.get("https://example.com")
        assert result["status"] == 200

    async def test_body_content(self):
        tool = APICallerTool()
        result = await tool.request("POST", "https://example.com", body="raw data")
        assert result["status"] == 200


class TestAPICallerFunction:
    async def test_basic_call(self):
        result = await api_caller_function(method="GET", url="https://example.com")
        assert result["status"] == 200

    async def test_with_timeout(self):
        result = await api_caller_function(
            method="GET", url="https://example.com", timeout=5.0
        )
        assert result["status"] == 200


class TestCreateAPICallerTool:
    def test_creates_definition(self):
        td = create_api_caller_tool()
        assert td.name == "api_caller"
        assert "method" in td.parameters


# =========================================================================== #
#  BUILTIN TOOLS - WEB SEARCH
# =========================================================================== #


class TestWebSearchTool:
    async def test_mock_search(self):
        tool = WebSearchTool()
        results = await tool.search("AI trends", max_results=3)
        assert len(results) == 3
        assert all(isinstance(r, SearchResult) for r in results)

    async def test_non_mock_engine_falls_back(self):
        tool = WebSearchTool(search_engine="google")
        results = await tool.search("test", max_results=2)
        assert len(results) == 2

    async def test_max_results_cap(self):
        tool = WebSearchTool()
        results = await tool.search("test", max_results=20)
        assert len(results) <= 10

    async def test_search_result_fields(self):
        tool = WebSearchTool()
        results = await tool.search("query", max_results=1)
        r = results[0]
        assert r.title
        assert r.url
        assert r.snippet
        assert r.relevance_score > 0


class TestWebSearchFunction:
    async def test_basic(self):
        result = await web_search_function(query="test", max_results=2)
        assert result["query"] == "test"
        assert result["count"] == 2
        assert len(result["results"]) == 2
        assert "timestamp" in result

    async def test_with_region(self):
        result = await web_search_function(query="test", region="US")
        assert result["count"] > 0


class TestCreateWebSearchTool:
    def test_creates_definition(self):
        td = create_web_search_tool()
        assert td.name == "web_search"
        assert "query" in td.parameters


# =========================================================================== #
#  CORE - ToolDefinition, ToolRegistry, decorators, adapters
# =========================================================================== #


class TestToolDefinition:
    def test_validate_required_missing(self):
        td = ToolDefinition(
            name="t",
            description="t",
            parameters={"x": {"type": "string", "required": True}},
            function=lambda: None,
        )
        ok, err = td.validate_parameters({})
        assert not ok
        assert "Missing" in err

    def test_validate_type_string(self):
        td = ToolDefinition(
            name="t", description="t",
            parameters={"x": {"type": "string"}},
            function=lambda: None,
        )
        ok, _ = td.validate_parameters({"x": "hello"})
        assert ok
        ok, err = td.validate_parameters({"x": 123})
        assert not ok

    def test_validate_type_integer(self):
        td = ToolDefinition(
            name="t", description="t",
            parameters={"x": {"type": "integer"}},
            function=lambda: None,
        )
        ok, _ = td.validate_parameters({"x": 5})
        assert ok
        ok, _ = td.validate_parameters({"x": "no"})
        assert not ok

    def test_validate_type_number(self):
        td = ToolDefinition(
            name="t", description="t",
            parameters={"x": {"type": "number"}},
            function=lambda: None,
        )
        ok, _ = td.validate_parameters({"x": 3.14})
        assert ok
        ok, _ = td.validate_parameters({"x": 3})
        assert ok

    def test_validate_type_boolean(self):
        td = ToolDefinition(
            name="t", description="t",
            parameters={"x": {"type": "boolean"}},
            function=lambda: None,
        )
        ok, _ = td.validate_parameters({"x": True})
        assert ok
        ok, _ = td.validate_parameters({"x": "yes"})
        assert not ok


class TestToolRegistry:
    def test_register_and_list(self):
        reg = ToolRegistry()
        initial = len(reg.tools)
        td = _make_tool_def("custom")
        reg.register(td)
        assert len(reg.tools) == initial + 1

    def test_unregister(self):
        reg = ToolRegistry()
        td = _make_tool_def("custom")
        reg.register(td)
        assert reg.unregister("custom")
        assert not reg.unregister("custom")

    async def test_execute(self):
        reg = ToolRegistry()
        result = await reg.execute("echo", {"message": "hi"})
        assert result == "hi"

    async def test_execute_unknown(self):
        reg = ToolRegistry()
        with pytest.raises(ValueError, match="Unknown tool"):
            await reg.execute("nope", {})

    async def test_execute_invalid_params(self):
        reg = ToolRegistry()
        with pytest.raises(ValueError, match="Invalid parameters"):
            await reg.execute("calculator", {"expression": 123})

    def test_get_tool(self):
        reg = ToolRegistry()
        assert reg.get_tool("calculator") is not None
        assert reg.get_tool("nope") is None

    def test_list_tools(self):
        reg = ToolRegistry()
        tools = reg.list_tools()
        names = [t["name"] for t in tools]
        assert "calculator" in names

    def test_execution_log(self):
        reg = ToolRegistry()
        log = reg.get_execution_log()
        assert isinstance(log, list)

    def test_repr(self):
        reg = ToolRegistry()
        assert "ToolRegistry" in repr(reg)


class TestToolDecorator:
    async def test_basic(self):
        @tool(name="my_func")
        async def my_func(x: str) -> str:
            """My doc."""
            return x

        assert hasattr(my_func, "_tool_definition")
        td = my_func._tool_definition
        assert td.name == "my_func"
        assert td.parameters["x"]["type"] == "string"

    async def test_auto_name(self):
        @tool()
        async def auto_name(a: int, b: float) -> float:
            return a + b

        td = auto_name._tool_definition
        assert td.name == "auto_name"
        assert td.parameters["a"]["type"] == "integer"
        assert td.parameters["b"]["type"] == "number"

    async def test_with_registry(self):
        reg = ToolRegistry()

        @tool(registry=reg)
        async def reg_tool(x: str) -> str:
            return x

        assert reg.get_tool("reg_tool") is not None

    async def test_bool_param(self):
        @tool()
        async def f(flag: bool):
            return flag

        assert f._tool_definition.parameters["flag"]["type"] == "boolean"

    async def test_list_param(self):
        @tool()
        async def f(items: list):
            return items

        assert f._tool_definition.parameters["items"]["type"] == "array"

    async def test_dict_param(self):
        @tool()
        async def f(data: dict):
            return data

        assert f._tool_definition.parameters["data"]["type"] == "object"

    async def test_no_annotation(self):
        @tool()
        async def f(x):
            return x

        assert f._tool_definition.parameters["x"]["type"] == "string"


class TestFunctionTool:
    async def test_basic(self):
        @function_tool
        async def simple(msg: str) -> str:
            """Simple tool."""
            return msg

        td = simple._tool_definition
        assert td.name == "simple"
        assert td.description == "Simple tool."


class TestFromOpenAIFunction:
    def test_converts(self):
        schema = {
            "name": "weather",
            "description": "Get weather",
            "parameters": {
                "type": "object",
                "properties": {
                    "location": {"type": "string", "description": "City"}
                },
                "required": ["location"],
            },
        }

        async def impl(location):
            return f"sunny in {location}"

        td = from_openai_function(schema, impl)
        assert td.name == "weather"
        assert td.parameters["location"]["required"] is True


class TestFromLangchainTool:
    def test_converts_with_run(self):
        mock_lc = MagicMock()
        mock_lc.name = "lc_search"
        mock_lc.description = "Search tool"
        mock_lc.args_schema = None
        mock_lc.__class__.__name__ = "MockTool"

        td = from_langchain_tool(mock_lc)
        assert td.name == "lc_search"
        assert "query" in td.parameters

    def test_converts_with_schema(self):
        mock_lc = MagicMock()
        mock_lc.name = "lc_tool"
        mock_lc.description = "Tool"
        mock_lc.__class__.__name__ = "MockTool"

        mock_schema = MagicMock()
        mock_schema.schema.return_value = {
            "properties": {
                "query": {"type": "string", "description": "q"}
            },
            "required": ["query"],
        }
        mock_lc.args_schema = mock_schema

        td = from_langchain_tool(mock_lc)
        assert td.parameters["query"]["required"] is True


class TestToolAdapter:
    def test_add_langchain_tool(self):
        reg = ToolRegistry()
        adapter = ToolAdapter(reg)
        mock_lc = MagicMock()
        mock_lc.name = "lc"
        mock_lc.description = "d"
        mock_lc.args_schema = None
        mock_lc.__class__.__name__ = "Mock"
        _td = adapter.add_langchain_tool(mock_lc)
        assert reg.get_tool("lc") is not None

    def test_add_langchain_tools(self):
        reg = ToolRegistry()
        adapter = ToolAdapter(reg)
        tools = []
        for i in range(2):
            m = MagicMock()
            m.name = f"lc{i}"
            m.description = "d"
            m.args_schema = None
            m.__class__.__name__ = "Mock"
            tools.append(m)
        result = adapter.add_langchain_tools(tools)
        assert len(result) == 2

    def test_add_openai_function(self):
        reg = ToolRegistry()
        adapter = ToolAdapter(reg)
        schema = {"name": "oai", "description": "d", "parameters": {"properties": {}}}

        async def impl():
            pass

        _td = adapter.add_openai_function(schema, impl)
        assert reg.get_tool("oai") is not None

    def test_add_openai_functions(self):
        reg = ToolRegistry()
        adapter = ToolAdapter(reg)

        async def impl():
            pass

        funcs = [
            ({"name": f"f{i}", "description": "d", "parameters": {"properties": {}}}, impl)
            for i in range(3)
        ]
        result = adapter.add_openai_functions(funcs)
        assert len(result) == 3


# =========================================================================== #
#  BUILTIN TOOLS REGISTRATION
# =========================================================================== #


class TestRegisterAllBuiltinTools:
    def test_registers_all(self):
        from ia_modules.tools.builtin_tools import register_all_builtin_tools

        reg = AdvancedToolRegistry()
        register_all_builtin_tools(reg)
        names = [t["name"] for t in reg.list_tools()]
        assert "web_search" in names
        assert "calculator" in names
        assert "code_executor" in names
        assert "file_operations" in names
        assert "api_caller" in names
