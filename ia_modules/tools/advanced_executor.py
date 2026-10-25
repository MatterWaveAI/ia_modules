"""
Advanced tool executor with planning, error handling, and caching.

Integrates all tool system components for production use.
"""

import logging
from typing import Any, Callable, Dict, List, Optional

from .tool_registry import AdvancedToolRegistry
from .tool_planner import ToolPlanner, Task, ExecutionPlan
from .tool_chain import ToolChain, ChainResult
from .parallel_executor import ParallelExecutor, ResourceLimits
from .error_handling import (
    CompositeErrorHandler,
    RetryConfig,
    CircuitBreakerConfig,
    FallbackConfig
)


class AdvancedToolExecutor:
    """
    Advanced tool executor with comprehensive features.

    Combines all tool system components:
    - Advanced registry with versioning and caching
    - Intelligent planning and task decomposition
    - Parallel execution with resource management
    - Tool chaining for complex workflows
    - Error handling (retry, circuit breaker, fallback)
    - Performance monitoring and analytics

    Example:
        >>> executor = AdvancedToolExecutor()
        >>>
        >>> # Register tools
        >>> executor.register_tool(my_tool, capabilities=["web_search"])
        >>>
        >>> # Execute with automatic planning
        >>> result = await executor.execute_task(
        ...     "Search for AI trends and summarize the results",
        ...     context={"max_results": 10}
        ... )
        >>>
        >>> # Execute specific tool with error handling
        >>> result = await executor.execute_tool(
        ...     "web_search",
        ...     {"query": "AI"},
        ...     retry=True,
        ...     cache_ttl=3600
        ... )
    """

    def __init__(
        self,
        enable_caching: bool = True,
        max_concurrent: int = 10,
        default_retry_config: Optional[RetryConfig] = None,
        default_circuit_breaker_config: Optional[CircuitBreakerConfig] = None
    ):
        """
        Initialize advanced tool executor.

        Args:
            enable_caching: Whether to enable result caching
            max_concurrent: Maximum concurrent tool executions
            default_retry_config: Default retry configuration
            default_circuit_breaker_config: Default circuit breaker configuration
        """
        self.registry = AdvancedToolRegistry(enable_caching=enable_caching)
        self.planner = ToolPlanner(self.registry)

        # Resource limits for parallel execution
        self.resource_limits = ResourceLimits(
            max_concurrent=max_concurrent,
            timeout_seconds=300.0
        )

        # Default error handling
        self.default_retry_config = default_retry_config or RetryConfig(
            max_attempts=3,
            initial_delay=1.0
        )
        self.default_circuit_breaker_config = default_circuit_breaker_config

        self.logger = logging.getLogger("AdvancedToolExecutor")

    def register_tool(
        self,
        tool: Any,
        version: str = "1.0.0",
        capabilities: Optional[List[str]] = None,
        set_as_default: bool = True
    ) -> None:
        """
        Register a tool.

        Args:
            tool: Tool definition
            version: Semantic version
            capabilities: List of capabilities this tool provides
            set_as_default: Whether to set as default version
        """
        self.registry.register_versioned(
            tool,
            version=version,
            capabilities=capabilities,
            set_as_default=set_as_default
        )

    async def execute_tool(
        self,
        tool_name: str,
        parameters: Dict[str, Any],
        version: Optional[str] = None,
        retry: bool = True,
        use_circuit_breaker: bool = False,
        cache_ttl: Optional[float] = None,
        fallback_tools: Optional[List[str]] = None
    ) -> Any:
        """
        Execute a single tool with error handling and caching.

        Args:
            tool_name: Tool to execute
            parameters: Tool parameters
            version: Specific version or None for default
            retry: Whether to retry on failure
            use_circuit_breaker: Whether to use circuit breaker
            cache_ttl: Cache time-to-live in seconds (None = no caching)
            fallback_tools: List of fallback tool names to try if primary fails

        Returns:
            Tool execution result
        """
        # Setup error handling
        retry_config = self.default_retry_config if retry else None
        circuit_breaker_config = self.default_circuit_breaker_config if use_circuit_breaker else None

        fallback_config = None
        if fallback_tools:
            # Create fallback functions
            fallback_funcs = [
                lambda t=tool, p=parameters: self.registry.execute(t, p, version)
                for tool in fallback_tools
            ]
            fallback_config = FallbackConfig(fallback_functions=fallback_funcs)

        error_handler = CompositeErrorHandler(
            retry_config=retry_config,
            circuit_breaker_config=circuit_breaker_config,
            fallback_config=fallback_config
        )

        # Execute function
        async def execute_func():
            if cache_ttl is not None:
                return await self.registry.execute_cached(
                    tool_name,
                    parameters,
                    ttl=cache_ttl,
                    version=version
                )
            else:
                return await self.registry.execute(tool_name, parameters, version)

        # Apply error handling
        if retry or use_circuit_breaker or fallback_tools:
            return await error_handler.execute(execute_func)
        else:
            return await execute_func()

    async def execute_task(
        self,
        task_description: str,
        requirements: Optional[List[str]] = None,
        context: Optional[Dict[str, Any]] = None,
        optimize_plan: bool = True,
        max_alternatives: int = 3
    ) -> Dict[str, Any]:
        """
        Execute a high-level task with automatic planning.

        Args:
            task_description: Natural language task description
            requirements: Required capabilities
            context: Initial context values
            optimize_plan: Whether to optimize the execution plan
            max_alternatives: Maximum alternative plans to generate

        Returns:
            Dictionary with execution results and metadata
        """
        self.logger.info(f"Executing task: {task_description}")

        # Create task
        task = Task(
            description=task_description,
            requirements=requirements or [],
            context=context or {}
        )

        # Create execution plan
        plan = await self.planner.create_plan(task, max_alternatives=max_alternatives)

        # Validate plan
        is_valid, issues = self.planner.validate_plan(plan)
        if not is_valid:
            raise ValueError(f"Invalid execution plan: {issues}")

        # Optimize if requested
        if optimize_plan:
            plan = self.planner.optimize_plan(plan)

        # Execute plan
        result = await self.execute_plan(plan, context=context)

        return {
            "success": result.success,
            "results": result.context,
            "steps_executed": result.steps_executed,
            "steps_skipped": result.steps_skipped,
            "errors": result.errors,
            "plan": {
                "complexity": plan.complexity.value,
                "estimated_time": plan.estimated_time,
                "confidence": plan.confidence
            }
        }

    async def execute_plan(
        self,
        plan: ExecutionPlan,
        context: Optional[Dict[str, Any]] = None
    ) -> ChainResult:
        """
        Execute an execution plan.

        Args:
            plan: Plan to execute
            context: Initial context values

        Returns:
            Chain execution result
        """
        # Create tool chain from plan
        chain = ToolChain(self._create_tool_executor())

        for step in plan.steps:
            # Map previous step outputs to this step's inputs
            input_mapping = step.get("input_mapping", {})

            # If no explicit mapping, use default based on capability
            if not input_mapping:
                input_mapping = self._infer_input_mapping(step, plan)

            chain.add_step(
                tool_name=step["tool_name"],
                input_mapping=input_mapping,
                output_key=f"step_{step.get('index', len(chain.steps))}_{step['capability']}",
                parallel_group=step.get("parallel_group")
            )

        # Execute chain
        result = await chain.execute(context)

        return result

    async def execute_parallel(
        self,
        tasks: List[tuple[str, Dict[str, Any]]],
        dependencies: Optional[Dict[str, List[str]]] = None
    ) -> Dict[str, Any]:
        """
        Execute multiple tools in parallel with dependencies.

        Args:
            tasks: List of (tool_name, parameters) tuples
            dependencies: Dictionary mapping task indices to dependency indices

        Returns:
            Dictionary mapping task IDs to results
        """
        parallel_executor = ParallelExecutor(
            tool_executor=self._create_tool_executor(),
            resource_limits=self.resource_limits
        )

        # Add tasks
        for i, (tool_name, parameters) in enumerate(tasks):
            task_id = f"task_{i}"
            deps = []

            if dependencies and str(i) in dependencies:
                deps = [f"task_{d}" for d in dependencies[str(i)]]

            parallel_executor.add_task(
                task_id=task_id,
                tool_name=tool_name,
                parameters=parameters,
                dependencies=deps
            )

        # Execute
        results = await parallel_executor.execute_all()

        return results

    async def execute_chain(
        self,
        steps: List[Dict[str, Any]],
        initial_context: Optional[Dict[str, Any]] = None
    ) -> ChainResult:
        """
        Execute a predefined chain of tools.

        Args:
            steps: List of step specifications with tool_name, input_mapping, output_key
            initial_context: Initial context values

        Returns:
            Chain execution result
        """
        chain = ToolChain(self._create_tool_executor())

        for step in steps:
            chain.add_step(
                tool_name=step["tool_name"],
                input_mapping=step["input_mapping"],
                output_key=step["output_key"],
                condition=step.get("condition"),
                on_error=step.get("on_error", "raise"),
                parallel_group=step.get("parallel_group")
            )

        result = await chain.execute(initial_context)

        return result

    def _create_tool_executor(self) -> Callable:
        """
        Create tool executor function for chains and parallel execution.

        Returns:
            Async function (tool_name, parameters) -> result
        """
        async def executor(tool_name: str, parameters: Dict[str, Any]) -> Any:
            return await self.execute_tool(
                tool_name,
                parameters,
                retry=True,
                cache_ttl=60.0  # 1 minute default cache
            )

        return executor

    def _infer_input_mapping(
        self,
        step: Dict[str, Any],
        plan: ExecutionPlan
    ) -> Dict[str, str]:
        """
        Infer input mapping for a step based on dependencies.

        Args:
            step: Step specification
            plan: Execution plan

        Returns:
            Input mapping dictionary
        """
        mapping: Dict[str, str] = {}

        # Get tool parameters
        tool = self.registry.get_tool(step["tool_name"], step.get("version"))
        if not tool:
            return mapping

        # Map each tool parameter to context
        for param_name, param_schema in tool.parameters.items():
            # Check dependencies for matching outputs
            dependencies = step.get("dependencies", [])

            if dependencies:
                # Use output from last dependency
                last_dep_idx = dependencies[-1]
                if last_dep_idx < len(plan.steps):
                    dep_step = plan.steps[last_dep_idx]
                    output_key = f"step_{dep_step.get('index', last_dep_idx)}_{dep_step['capability']}"
                    mapping[param_name] = output_key
            else:
                # No dependencies - expect parameter in initial context
                mapping[param_name] = param_name

        return mapping

    def get_statistics(self) -> Dict[str, Any]:
        """
        Get executor statistics.

        Returns:
            Statistics dictionary
        """
        return {
            "registry": self.registry.get_statistics(),
            "cache_size": len(self.registry.cache),
            "total_tools": sum(len(versions) for versions in self.registry.tools.values()),
            "capabilities": self.registry.list_capabilities()
        }

    def clear_cache(self) -> int:
        """
        Clear result cache.

        Returns:
            Number of entries cleared
        """
        return self.registry.clear_cache()

    def list_tools(
        self,
        capability: Optional[str] = None,
        include_deprecated: bool = False
    ) -> List[Dict[str, Any]]:
        """
        List registered tools.

        Args:
            capability: Filter by capability
            include_deprecated: Include deprecated versions

        Returns:
            List of tool information
        """
        return self.registry.list_tools(
            include_deprecated=include_deprecated,
            capability=capability
        )

    def export_catalog(self) -> Dict[str, Any]:
        """
        Export complete tool catalog.

        Returns:
            Catalog dictionary
        """
        return self.registry.export_tool_catalog()
