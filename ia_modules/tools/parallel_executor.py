"""
Parallel tool execution with resource management and dependency handling.

Enables concurrent execution of multiple tools with proper coordination.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Dict, List, Optional, Set
from collections import defaultdict


class ExecutionStatus(Enum):
    """Status of tool execution."""
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@dataclass
class ExecutionTask:
    """
    Represents a tool execution task.

    Attributes:
        task_id: Unique task identifier
        tool_name: Name of tool to execute
        parameters: Tool parameters
        dependencies: Set of task IDs this task depends on
        status: Current execution status
        result: Execution result (if completed)
        error: Error message (if failed)
        started_at: When execution started
        completed_at: When execution completed
        priority: Task priority (higher = more important)
    """
    task_id: str
    tool_name: str
    parameters: Dict[str, Any]
    dependencies: Set[str] = field(default_factory=set)
    status: ExecutionStatus = ExecutionStatus.PENDING
    result: Any = None
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    priority: int = 0


@dataclass
class ResourceLimits:
    """
    Resource limits for parallel execution.

    Attributes:
        max_concurrent: Maximum concurrent executions
        max_memory_mb: Maximum memory usage in MB (0 = unlimited)
        max_cpu_percent: Maximum CPU usage percentage (0 = unlimited)
        timeout_seconds: Maximum execution time per task (0 = unlimited)
    """
    max_concurrent: int = 10
    max_memory_mb: int = 0
    max_cpu_percent: int = 0
    timeout_seconds: float = 300.0


class ParallelExecutor:
    """
    Executes multiple tools in parallel with dependency management.

    Features:
    - Concurrent execution with configurable limits
    - Dependency resolution and ordering
    - Priority-based scheduling
    - Resource management
    - Progress tracking
    - Error handling and cancellation

    Example:
        >>> executor = ParallelExecutor(max_concurrent=5)
        >>>
        >>> # Add tasks
        >>> executor.add_task("task1", "web_search", {"query": "AI"})
        >>> executor.add_task("task2", "summarize", {"text": "..."}, dependencies=["task1"])
        >>>
        >>> # Execute all
        >>> results = await executor.execute_all()
    """

    def __init__(
        self,
        tool_executor: Callable,
        resource_limits: Optional[ResourceLimits] = None
    ):
        """
        Initialize parallel executor.

        Args:
            tool_executor: Async function to execute tools (tool_name, params) -> result
            resource_limits: Resource limits configuration
        """
        self.tool_executor = tool_executor
        self.resource_limits = resource_limits or ResourceLimits()

        self.tasks: Dict[str, ExecutionTask] = {}
        self.semaphore = asyncio.Semaphore(self.resource_limits.max_concurrent)

        self.logger = logging.getLogger("ParallelExecutor")

    def add_task(
        self,
        task_id: str,
        tool_name: str,
        parameters: Dict[str, Any],
        dependencies: Optional[List[str]] = None,
        priority: int = 0
    ) -> None:
        """
        Add a task to the execution queue.

        Args:
            task_id: Unique task identifier
            tool_name: Tool to execute
            parameters: Tool parameters
            dependencies: List of task IDs this depends on
            priority: Task priority (higher = more important)
        """
        if task_id in self.tasks:
            raise ValueError(f"Task {task_id} already exists")

        deps = set(dependencies) if dependencies else set()

        # Validate dependencies exist
        for dep in deps:
            if dep not in self.tasks and dep != task_id:
                self.logger.warning(f"Dependency {dep} not found for task {task_id}")

        task = ExecutionTask(
            task_id=task_id,
            tool_name=tool_name,
            parameters=parameters,
            dependencies=deps,
            priority=priority
        )

        self.tasks[task_id] = task
        self.logger.debug(f"Added task {task_id}: {tool_name}")

    def remove_task(self, task_id: str) -> bool:
        """
        Remove a task from the queue.

        Args:
            task_id: Task to remove

        Returns:
            True if removed, False if not found
        """
        if task_id in self.tasks:
            task = self.tasks[task_id]
            if task.status == ExecutionStatus.RUNNING:
                self.logger.warning(f"Cannot remove running task {task_id}")
                return False

            del self.tasks[task_id]
            self.logger.debug(f"Removed task {task_id}")
            return True

        return False

    def _get_ready_tasks(self) -> List[ExecutionTask]:
        """
        Get tasks that are ready to execute.

        Returns:
            List of tasks with all dependencies completed
        """
        ready = []

        for task in self.tasks.values():
            if task.status != ExecutionStatus.PENDING:
                continue

            # Check if all dependencies are completed
            deps_completed = all(
                self.tasks[dep_id].status == ExecutionStatus.COMPLETED
                for dep_id in task.dependencies
                if dep_id in self.tasks
            )

            if deps_completed:
                ready.append(task)

        # Sort by priority (higher first)
        ready.sort(key=lambda t: t.priority, reverse=True)

        return ready

    async def _execute_task(self, task: ExecutionTask) -> None:
        """
        Execute a single task.

        Args:
            task: Task to execute
        """
        task.status = ExecutionStatus.RUNNING
        task.started_at = datetime.now(timezone.utc)

        self.logger.info(f"Executing task {task.task_id}: {task.tool_name}")

        try:
            # Execute with timeout
            if self.resource_limits.timeout_seconds > 0:
                result = await asyncio.wait_for(
                    self.tool_executor(task.tool_name, task.parameters),
                    timeout=self.resource_limits.timeout_seconds
                )
            else:
                result = await self.tool_executor(task.tool_name, task.parameters)

            task.result = result
            task.status = ExecutionStatus.COMPLETED
            self.logger.info(f"Task {task.task_id} completed successfully")

        except asyncio.TimeoutError:
            task.error = f"Task timed out after {self.resource_limits.timeout_seconds}s"
            task.status = ExecutionStatus.FAILED
            self.logger.error(f"Task {task.task_id} timed out")

        except Exception as e:
            task.error = str(e)
            task.status = ExecutionStatus.FAILED
            self.logger.error(f"Task {task.task_id} failed: {e}")

        finally:
            task.completed_at = datetime.now(timezone.utc)

    async def _execute_with_semaphore(self, task: ExecutionTask) -> None:
        """
        Execute task with resource limiting.

        Args:
            task: Task to execute
        """
        async with self.semaphore:
            await self._execute_task(task)

    async def execute_all(self, fail_fast: bool = False) -> Dict[str, Any]:
        """
        Execute all tasks with dependency resolution.

        Args:
            fail_fast: Whether to stop on first failure

        Returns:
            Dictionary mapping task_id -> result
        """
        if not self.tasks:
            return {}

        self.logger.info(f"Executing {len(self.tasks)} tasks with max_concurrent={self.resource_limits.max_concurrent}")

        # Detect circular dependencies
        if self._has_circular_dependencies():
            raise ValueError("Circular dependencies detected")

        # Execute tasks in waves
        while True:
            ready_tasks = self._get_ready_tasks()

            if not ready_tasks:
                # Check if all tasks completed
                pending = [t for t in self.tasks.values() if t.status == ExecutionStatus.PENDING]
                running = [t for t in self.tasks.values() if t.status == ExecutionStatus.RUNNING]

                if not pending and not running:
                    break  # All done

                if not running:
                    # Tasks pending but none ready - dependency issue
                    raise ValueError("Deadlock detected: pending tasks with unmet dependencies")

                # Wait for running tasks
                await asyncio.sleep(0.1)
                continue

            # Launch ready tasks
            tasks_to_run = [
                self._execute_with_semaphore(task)
                for task in ready_tasks
            ]

            # Wait for this batch to complete
            await asyncio.gather(*tasks_to_run, return_exceptions=not fail_fast)

            # Check for failures in fail_fast mode
            if fail_fast:
                failed = [t for t in self.tasks.values() if t.status == ExecutionStatus.FAILED]
                if failed:
                    self.logger.error(f"Stopping execution due to failures: {[t.task_id for t in failed]}")
                    break

        # Collect results
        results = {}
        for task_id, task in self.tasks.items():
            if task.status == ExecutionStatus.COMPLETED:
                results[task_id] = task.result
            elif task.status == ExecutionStatus.FAILED:
                results[task_id] = {"error": task.error}

        return results

    async def execute_task(self, task_id: str) -> Any:
        """
        Execute a single task (and its dependencies if needed).

        Args:
            task_id: Task to execute

        Returns:
            Task result

        Raises:
            ValueError: If task not found
        """
        if task_id not in self.tasks:
            raise ValueError(f"Task not found: {task_id}")

        task = self.tasks[task_id]

        # Execute dependencies first
        for dep_id in task.dependencies:
            if dep_id in self.tasks:
                dep_task = self.tasks[dep_id]
                if dep_task.status == ExecutionStatus.PENDING:
                    await self.execute_task(dep_id)

        # Execute this task
        if task.status == ExecutionStatus.PENDING:
            await self._execute_with_semaphore(task)

        if task.status == ExecutionStatus.FAILED:
            raise Exception(f"Task failed: {task.error}")

        return task.result

    def cancel_task(self, task_id: str) -> bool:
        """
        Cancel a pending task.

        Args:
            task_id: Task to cancel

        Returns:
            True if cancelled, False if not found or already running
        """
        if task_id not in self.tasks:
            return False

        task = self.tasks[task_id]
        if task.status == ExecutionStatus.PENDING:
            task.status = ExecutionStatus.CANCELLED
            self.logger.info(f"Cancelled task {task_id}")
            return True

        return False

    def get_status(self, task_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Get execution status.

        Args:
            task_id: Specific task or None for all

        Returns:
            Status information
        """
        if task_id:
            if task_id not in self.tasks:
                return {"error": "Task not found"}

            task = self.tasks[task_id]
            return {
                "task_id": task.task_id,
                "tool_name": task.tool_name,
                "status": task.status.value,
                "started_at": task.started_at.isoformat() if task.started_at else None,
                "completed_at": task.completed_at.isoformat() if task.completed_at else None,
                "dependencies": list(task.dependencies),
                "error": task.error
            }

        # All tasks
        by_status = defaultdict(list)
        for task in self.tasks.values():
            by_status[task.status.value].append(task.task_id)

        return {
            "total_tasks": len(self.tasks),
            "by_status": dict(by_status),
            "ready_tasks": len(self._get_ready_tasks())
        }

    def _has_circular_dependencies(self) -> bool:
        """
        Check for circular dependencies using DFS.

        Returns:
            True if circular dependencies exist
        """
        visited = set()
        rec_stack = set()

        def visit(task_id: str) -> bool:
            if task_id in rec_stack:
                return True  # Cycle detected

            if task_id in visited:
                return False

            visited.add(task_id)
            rec_stack.add(task_id)

            task = self.tasks.get(task_id)
            if task:
                for dep_id in task.dependencies:
                    if visit(dep_id):
                        return True

            rec_stack.remove(task_id)
            return False

        for task_id in self.tasks:
            if task_id not in visited:
                if visit(task_id):
                    return True

        return False

    def clear(self) -> None:
        """Clear all tasks."""
        self.tasks.clear()
        self.logger.info("Cleared all tasks")

    def get_execution_graph(self) -> Dict[str, Any]:
        """
        Get dependency graph representation.

        Returns:
            Graph with nodes and edges
        """
        nodes = []
        edges = []

        for task in self.tasks.values():
            nodes.append({
                "id": task.task_id,
                "tool": task.tool_name,
                "status": task.status.value,
                "priority": task.priority
            })

            for dep_id in task.dependencies:
                edges.append({
                    "from": dep_id,
                    "to": task.task_id
                })

        return {
            "nodes": nodes,
            "edges": edges
        }
