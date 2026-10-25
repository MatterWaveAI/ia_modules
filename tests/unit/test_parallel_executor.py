"""
Unit tests for parallel tool execution.

Tests ParallelExecutor, ExecutionTask, dependency resolution,
concurrency limiting, timeouts, and status tracking.
"""

import asyncio
from unittest.mock import AsyncMock

import pytest

from ia_modules.tools.parallel_executor import (
    ParallelExecutor,
    ExecutionTask,
    ExecutionStatus,
    ResourceLimits,
)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #


def _make_executor(tool_executor=None, **limits_kwargs):
    """Create a ParallelExecutor with a mock tool_executor."""
    if tool_executor is None:
        tool_executor = AsyncMock(return_value="result")
    limits = ResourceLimits(**limits_kwargs) if limits_kwargs else None
    return ParallelExecutor(tool_executor=tool_executor, resource_limits=limits)


# --------------------------------------------------------------------------- #
# ExecutionTask dataclass
# --------------------------------------------------------------------------- #


class TestExecutionTask:
    """Test ExecutionTask dataclass."""

    def test_defaults(self):
        """ExecutionTask has correct defaults."""
        task = ExecutionTask(task_id="t1", tool_name="search", parameters={"q": "test"})
        assert task.status == ExecutionStatus.PENDING
        assert task.result is None
        assert task.error is None
        assert task.started_at is None
        assert task.completed_at is None
        assert task.priority == 0
        assert task.dependencies == set()


class TestExecutionStatus:
    """Test ExecutionStatus enum values."""

    def test_all_statuses_defined(self):
        """All expected statuses exist."""
        assert ExecutionStatus.PENDING.value == "pending"
        assert ExecutionStatus.RUNNING.value == "running"
        assert ExecutionStatus.COMPLETED.value == "completed"
        assert ExecutionStatus.FAILED.value == "failed"
        assert ExecutionStatus.CANCELLED.value == "cancelled"


class TestResourceLimits:
    """Test ResourceLimits defaults."""

    def test_defaults(self):
        """ResourceLimits has correct default values."""
        limits = ResourceLimits()
        assert limits.max_concurrent == 10
        assert limits.max_memory_mb == 0
        assert limits.max_cpu_percent == 0
        assert limits.timeout_seconds == 300.0


# --------------------------------------------------------------------------- #
# ParallelExecutor — task management
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
class TestParallelExecutorTaskManagement:
    """Test adding, removing, and querying tasks."""

    async def test_add_task(self):
        """Tasks can be added to the executor."""
        executor = _make_executor()
        executor.add_task("t1", "search", {"q": "ai"})

        assert "t1" in executor.tasks
        assert executor.tasks["t1"].tool_name == "search"

    async def test_add_duplicate_task_raises(self):
        """Adding a task with an existing ID raises ValueError."""
        executor = _make_executor()
        executor.add_task("t1", "search", {"q": "ai"})

        with pytest.raises(ValueError, match="already exists"):
            executor.add_task("t1", "search", {"q": "other"})

    async def test_add_task_with_dependencies(self):
        """Tasks can declare dependencies."""
        executor = _make_executor()
        executor.add_task("t1", "search", {})
        executor.add_task("t2", "summarize", {}, dependencies=["t1"])

        assert "t1" in executor.tasks["t2"].dependencies

    async def test_add_task_with_priority(self):
        """Tasks can be assigned a priority."""
        executor = _make_executor()
        executor.add_task("t1", "search", {}, priority=10)

        assert executor.tasks["t1"].priority == 10

    async def test_remove_task(self):
        """Pending tasks can be removed."""
        executor = _make_executor()
        executor.add_task("t1", "search", {})

        result = executor.remove_task("t1")

        assert result is True
        assert "t1" not in executor.tasks

    async def test_remove_nonexistent_task(self):
        """Removing a nonexistent task returns False."""
        executor = _make_executor()
        assert executor.remove_task("missing") is False

    async def test_remove_running_task_blocked(self):
        """Running tasks cannot be removed."""
        executor = _make_executor()
        executor.add_task("t1", "search", {})
        executor.tasks["t1"].status = ExecutionStatus.RUNNING

        assert executor.remove_task("t1") is False
        assert "t1" in executor.tasks

    async def test_cancel_task(self):
        """Pending tasks can be cancelled."""
        executor = _make_executor()
        executor.add_task("t1", "search", {})

        result = executor.cancel_task("t1")

        assert result is True
        assert executor.tasks["t1"].status == ExecutionStatus.CANCELLED

    async def test_cancel_nonexistent_task(self):
        """Cancelling a nonexistent task returns False."""
        executor = _make_executor()
        assert executor.cancel_task("missing") is False

    async def test_cancel_running_task_returns_false(self):
        """Running tasks cannot be cancelled."""
        executor = _make_executor()
        executor.add_task("t1", "search", {})
        executor.tasks["t1"].status = ExecutionStatus.RUNNING

        assert executor.cancel_task("t1") is False

    async def test_clear_removes_all_tasks(self):
        """clear() empties the task queue."""
        executor = _make_executor()
        executor.add_task("t1", "a", {})
        executor.add_task("t2", "b", {})

        executor.clear()

        assert len(executor.tasks) == 0


# --------------------------------------------------------------------------- #
# ParallelExecutor — execution
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
class TestParallelExecutorExecution:
    """Test concurrent execution, result collection, and error handling."""

    async def test_execute_all_empty(self):
        """execute_all with no tasks returns empty dict."""
        executor = _make_executor()
        results = await executor.execute_all()
        assert results == {}

    async def test_execute_all_single_task(self):
        """Single task is executed and result collected."""
        mock_exec = AsyncMock(return_value="search_result")
        executor = _make_executor(tool_executor=mock_exec)
        executor.add_task("t1", "search", {"q": "ai"})

        results = await executor.execute_all()

        assert results["t1"] == "search_result"
        mock_exec.assert_awaited_once_with("search", {"q": "ai"})

    async def test_execute_all_multiple_independent_tasks(self):
        """Multiple independent tasks execute and return results."""
        call_log = []

        async def mock_exec(tool_name, params):
            call_log.append(tool_name)
            return f"{tool_name}_result"

        executor = _make_executor(tool_executor=mock_exec)
        executor.add_task("t1", "search", {})
        executor.add_task("t2", "calculate", {})
        executor.add_task("t3", "echo", {})

        results = await executor.execute_all()

        assert results["t1"] == "search_result"
        assert results["t2"] == "calculate_result"
        assert results["t3"] == "echo_result"
        assert len(call_log) == 3

    async def test_execute_all_respects_dependencies(self):
        """Tasks with dependencies wait for them to complete."""
        execution_order = []

        async def mock_exec(tool_name, params):
            execution_order.append(tool_name)
            return f"{tool_name}_done"

        executor = _make_executor(tool_executor=mock_exec)
        executor.add_task("t1", "fetch", {})
        executor.add_task("t2", "process", {}, dependencies=["t1"])

        results = await executor.execute_all()

        assert execution_order.index("fetch") < execution_order.index("process")
        assert results["t1"] == "fetch_done"
        assert results["t2"] == "process_done"

    async def test_execute_all_task_failure_recorded(self):
        """Failed tasks have their error recorded in results."""
        async def mock_exec(tool_name, params):
            if tool_name == "bad":
                raise RuntimeError("something broke")
            return "ok"

        executor = _make_executor(tool_executor=mock_exec)
        executor.add_task("t1", "bad", {})
        executor.add_task("t2", "good", {})

        results = await executor.execute_all()

        assert results["t1"] == {"error": "something broke"}
        assert results["t2"] == "ok"

    async def test_execute_all_fail_fast(self):
        """fail_fast=True stops execution on first failure."""
        async def mock_exec(tool_name, params):
            if tool_name == "bad":
                raise RuntimeError("boom")
            return "ok"

        executor = _make_executor(tool_executor=mock_exec)
        executor.add_task("t1", "bad", {}, priority=10)
        executor.add_task("t2", "good", {}, priority=0)

        results = await executor.execute_all(fail_fast=True)

        assert results["t1"] == {"error": "boom"}

    async def test_execute_all_timeout(self):
        """Tasks exceeding timeout are marked as failed."""
        async def slow_exec(tool_name, params):
            await asyncio.sleep(10)
            return "done"

        executor = _make_executor(tool_executor=slow_exec, timeout_seconds=0.1)
        executor.add_task("t1", "slow", {})

        results = await executor.execute_all()

        assert "error" in results["t1"]
        assert "timed out" in results["t1"]["error"]
        assert executor.tasks["t1"].status == ExecutionStatus.FAILED

    async def test_execute_all_priority_ordering(self):
        """Higher-priority tasks are started first within a wave."""
        execution_order = []

        async def mock_exec(tool_name, params):
            execution_order.append(tool_name)
            return "ok"

        executor = _make_executor(tool_executor=mock_exec, max_concurrent=1)
        executor.add_task("low", "low_tool", {}, priority=1)
        executor.add_task("high", "high_tool", {}, priority=10)

        await executor.execute_all()

        # high priority should execute first
        assert execution_order[0] == "high_tool"

    async def test_execute_all_circular_dependency_raises(self):
        """Circular dependencies raise ValueError."""
        executor = _make_executor()
        executor.add_task("t1", "a", {}, dependencies=["t2"])
        executor.add_task("t2", "b", {}, dependencies=["t1"])

        with pytest.raises(ValueError, match="Circular dependencies"):
            await executor.execute_all()

    async def test_execute_all_sets_timestamps(self):
        """Executed tasks have started_at and completed_at set."""
        mock_exec = AsyncMock(return_value="ok")
        executor = _make_executor(tool_executor=mock_exec)
        executor.add_task("t1", "search", {})

        await executor.execute_all()

        task = executor.tasks["t1"]
        assert task.started_at is not None
        assert task.completed_at is not None
        assert task.completed_at >= task.started_at

    async def test_execute_all_concurrency_limited(self):
        """Semaphore limits concurrent executions."""
        max_concurrent_seen = 0
        current_concurrent = 0
        lock = asyncio.Lock()

        async def mock_exec(tool_name, params):
            nonlocal max_concurrent_seen, current_concurrent
            async with lock:
                current_concurrent += 1
                if current_concurrent > max_concurrent_seen:
                    max_concurrent_seen = current_concurrent
            await asyncio.sleep(0.05)
            async with lock:
                current_concurrent -= 1
            return "ok"

        executor = _make_executor(tool_executor=mock_exec, max_concurrent=2)
        for i in range(5):
            executor.add_task(f"t{i}", "work", {})

        await executor.execute_all()

        assert max_concurrent_seen <= 2


# --------------------------------------------------------------------------- #
# ParallelExecutor — execute single task
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
class TestParallelExecutorSingleTask:
    """Test executing a single task (with dependency resolution)."""

    async def test_execute_single_task(self):
        """execute_task runs a single task by ID."""
        mock_exec = AsyncMock(return_value="result")
        executor = _make_executor(tool_executor=mock_exec)
        executor.add_task("t1", "search", {"q": "test"})

        result = await executor.execute_task("t1")

        assert result == "result"

    async def test_execute_single_task_not_found(self):
        """execute_task raises ValueError for unknown task ID."""
        executor = _make_executor()

        with pytest.raises(ValueError, match="Task not found"):
            await executor.execute_task("missing")

    async def test_execute_single_task_runs_dependencies(self):
        """execute_task automatically runs dependencies first."""
        execution_order = []

        async def mock_exec(tool_name, params):
            execution_order.append(tool_name)
            return f"{tool_name}_done"

        executor = _make_executor(tool_executor=mock_exec)
        executor.add_task("dep", "fetch", {})
        executor.add_task("main", "process", {}, dependencies=["dep"])

        result = await executor.execute_task("main")

        assert execution_order == ["fetch", "process"]
        assert result == "process_done"

    async def test_execute_single_task_failure_raises(self):
        """execute_task raises if the task fails."""
        async def mock_exec(tool_name, params):
            raise RuntimeError("broken")

        executor = _make_executor(tool_executor=mock_exec)
        executor.add_task("t1", "bad", {})

        with pytest.raises(Exception, match="Task failed"):
            await executor.execute_task("t1")


# --------------------------------------------------------------------------- #
# ParallelExecutor — status & graph
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
class TestParallelExecutorStatus:
    """Test status reporting and execution graph."""

    async def test_get_status_all(self):
        """get_status() returns summary of all tasks."""
        executor = _make_executor()
        executor.add_task("t1", "a", {})
        executor.add_task("t2", "b", {})

        status = executor.get_status()

        assert status["total_tasks"] == 2
        assert "pending" in status["by_status"]
        assert len(status["by_status"]["pending"]) == 2

    async def test_get_status_single(self):
        """get_status(task_id) returns details for one task."""
        executor = _make_executor()
        executor.add_task("t1", "search", {"q": "ai"}, dependencies=["dep1"])

        status = executor.get_status("t1")

        assert status["task_id"] == "t1"
        assert status["tool_name"] == "search"
        assert status["status"] == "pending"
        assert "dep1" in status["dependencies"]

    async def test_get_status_unknown_task(self):
        """get_status for unknown task returns error."""
        executor = _make_executor()
        status = executor.get_status("missing")
        assert "error" in status

    async def test_get_execution_graph(self):
        """get_execution_graph returns nodes and edges."""
        executor = _make_executor()
        executor.add_task("t1", "fetch", {})
        executor.add_task("t2", "process", {}, dependencies=["t1"])

        graph = executor.get_execution_graph()

        assert len(graph["nodes"]) == 2
        assert len(graph["edges"]) == 1
        assert graph["edges"][0]["from"] == "t1"
        assert graph["edges"][0]["to"] == "t2"

    async def test_get_ready_tasks(self):
        """_get_ready_tasks returns only tasks with completed dependencies."""
        executor = _make_executor()
        executor.add_task("t1", "a", {})
        executor.add_task("t2", "b", {}, dependencies=["t1"])

        ready = executor._get_ready_tasks()

        # Only t1 is ready (t2 depends on t1 which is still pending)
        assert len(ready) == 1
        assert ready[0].task_id == "t1"

    async def test_get_ready_tasks_after_dependency_completed(self):
        """Dependent tasks become ready after dependencies complete."""
        executor = _make_executor()
        executor.add_task("t1", "a", {})
        executor.add_task("t2", "b", {}, dependencies=["t1"])

        # Mark t1 as completed
        executor.tasks["t1"].status = ExecutionStatus.COMPLETED

        ready = executor._get_ready_tasks()

        assert len(ready) == 1
        assert ready[0].task_id == "t2"


# --------------------------------------------------------------------------- #
# Circular dependency detection
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
class TestCircularDependencyDetection:
    """Test _has_circular_dependencies."""

    async def test_no_circular_deps(self):
        """Linear dependency chain is not circular."""
        executor = _make_executor()
        executor.add_task("t1", "a", {})
        executor.add_task("t2", "b", {}, dependencies=["t1"])
        executor.add_task("t3", "c", {}, dependencies=["t2"])

        assert executor._has_circular_dependencies() is False

    async def test_direct_circular_deps(self):
        """Direct circular dependency detected."""
        executor = _make_executor()
        executor.add_task("t1", "a", {}, dependencies=["t2"])
        executor.add_task("t2", "b", {}, dependencies=["t1"])

        assert executor._has_circular_dependencies() is True

    async def test_indirect_circular_deps(self):
        """Indirect circular dependency detected."""
        executor = _make_executor()
        executor.add_task("t1", "a", {}, dependencies=["t3"])
        executor.add_task("t2", "b", {}, dependencies=["t1"])
        executor.add_task("t3", "c", {}, dependencies=["t2"])

        assert executor._has_circular_dependencies() is True

    async def test_no_deps_no_cycle(self):
        """Tasks with no dependencies have no cycles."""
        executor = _make_executor()
        executor.add_task("t1", "a", {})
        executor.add_task("t2", "b", {})

        assert executor._has_circular_dependencies() is False
