"""
Tool chaining for composing multiple tools into workflows.

Enables building complex workflows by connecting tool outputs to inputs.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from enum import Enum


class ChainMode(Enum):
    """Chain execution modes."""
    SEQUENTIAL = "sequential"  # Execute tools one after another
    PARALLEL = "parallel"  # Execute independent tools concurrently
    CONDITIONAL = "conditional"  # Execute based on conditions


@dataclass
class ChainStep:
    """
    A step in a tool chain.

    Attributes:
        tool_name: Name of tool to execute
        input_mapping: Map chain context keys to tool parameters
        output_key: Key to store result in context
        condition: Optional condition function to check before execution
        on_error: Error handling strategy ("raise", "skip", "default")
        default_value: Default value if error and on_error="default"
        parallel_group: Group ID for parallel execution
    """
    tool_name: str
    input_mapping: Dict[str, str]  # tool_param -> context_key
    output_key: str
    condition: Optional[Callable[[Dict[str, Any]], bool]] = None
    on_error: str = "raise"  # "raise", "skip", "default"
    default_value: Any = None
    parallel_group: Optional[int] = None


@dataclass
class ChainResult:
    """
    Result of chain execution.

    Attributes:
        success: Whether chain completed successfully
        context: Final execution context with all results
        steps_executed: List of step output keys that were executed
        steps_skipped: List of step output keys that were skipped
        errors: Dictionary of errors by step output key
    """
    success: bool
    context: Dict[str, Any]
    steps_executed: List[str] = field(default_factory=list)
    steps_skipped: List[str] = field(default_factory=list)
    errors: Dict[str, str] = field(default_factory=dict)


class ToolChain:
    """
    Chains multiple tools together with data flow.

    Features:
    - Sequential and parallel execution
    - Input/output mapping between steps
    - Conditional execution
    - Error handling strategies
    - Context management
    - Progress tracking

    Example:
        >>> chain = ToolChain(tool_executor)
        >>>
        >>> # Add steps
        >>> chain.add_step("web_search", {"query": "input_query"}, "search_results")
        >>> chain.add_step("summarize", {"text": "search_results"}, "summary")
        >>> chain.add_step("translate", {"text": "summary"}, "translated")
        >>>
        >>> # Execute
        >>> result = await chain.execute({"input_query": "AI trends"})
        >>> print(result.context["translated"])
    """

    def __init__(self, tool_executor: Callable):
        """
        Initialize tool chain.

        Args:
            tool_executor: Async function to execute tools (tool_name, params) -> result
        """
        self.tool_executor = tool_executor
        self.steps: List[ChainStep] = []
        self.logger = logging.getLogger("ToolChain")

    def add_step(
        self,
        tool_name: str,
        input_mapping: Dict[str, str],
        output_key: str,
        condition: Optional[Callable[[Dict[str, Any]], bool]] = None,
        on_error: str = "raise",
        default_value: Any = None,
        parallel_group: Optional[int] = None
    ) -> "ToolChain":
        """
        Add a step to the chain.

        Args:
            tool_name: Tool to execute
            input_mapping: Map tool parameters to context keys
            output_key: Key to store result
            condition: Optional condition to check before execution
            on_error: Error handling ("raise", "skip", "default")
            default_value: Default value if error occurs
            parallel_group: Group for parallel execution

        Returns:
            Self for method chaining
        """
        step = ChainStep(
            tool_name=tool_name,
            input_mapping=input_mapping,
            output_key=output_key,
            condition=condition,
            on_error=on_error,
            default_value=default_value,
            parallel_group=parallel_group
        )

        self.steps.append(step)
        self.logger.debug(f"Added step: {tool_name} -> {output_key}")
        return self

    def add_parallel_steps(
        self,
        steps: List[tuple[str, Dict[str, str], str]],
        parallel_group: Optional[int] = None
    ) -> "ToolChain":
        """
        Add multiple steps to execute in parallel.

        Args:
            steps: List of (tool_name, input_mapping, output_key) tuples
            parallel_group: Group ID for these steps

        Returns:
            Self for method chaining
        """
        if parallel_group is None:
            # Auto-assign group ID
            existing_groups = [s.parallel_group for s in self.steps if s.parallel_group is not None]
            parallel_group = max(existing_groups) + 1 if existing_groups else 0

        for tool_name, input_mapping, output_key in steps:
            self.add_step(
                tool_name=tool_name,
                input_mapping=input_mapping,
                output_key=output_key,
                parallel_group=parallel_group
            )

        return self

    def _prepare_tool_params(
        self,
        step: ChainStep,
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Prepare tool parameters from context.

        Args:
            step: Chain step
            context: Execution context

        Returns:
            Tool parameters

        Raises:
            KeyError: If required context key not found
        """
        params = {}

        for tool_param, context_key in step.input_mapping.items():
            if context_key not in context:
                raise KeyError(f"Required context key not found: {context_key}")
            params[tool_param] = context[context_key]

        return params

    async def _execute_step(
        self,
        step: ChainStep,
        context: Dict[str, Any]
    ) -> tuple[bool, Any, Optional[str]]:
        """
        Execute a single step.

        Args:
            step: Step to execute
            context: Execution context

        Returns:
            Tuple of (success, result, error_message)
        """
        # Check condition
        if step.condition and not step.condition(context):
            self.logger.debug(f"Skipping step {step.output_key} (condition not met)")
            return False, None, None

        try:
            # Prepare parameters
            params = self._prepare_tool_params(step, context)

            # Execute tool
            self.logger.info(f"Executing step: {step.tool_name} -> {step.output_key}")
            result = await self.tool_executor(step.tool_name, params)

            return True, result, None

        except Exception as e:
            error_msg = str(e)
            self.logger.error(f"Step {step.output_key} failed: {error_msg}")

            if step.on_error == "raise":
                raise
            elif step.on_error == "default":
                return True, step.default_value, error_msg
            else:  # skip
                return False, None, error_msg

    async def execute(
        self,
        initial_context: Optional[Dict[str, Any]] = None
    ) -> ChainResult:
        """
        Execute the tool chain.

        Args:
            initial_context: Initial context values

        Returns:
            ChainResult with execution details
        """
        context = initial_context.copy() if initial_context else {}
        steps_executed = []
        steps_skipped = []
        errors = {}

        self.logger.info(f"Executing chain with {len(self.steps)} steps")

        # Group steps by parallel group
        sequential_steps = [s for s in self.steps if s.parallel_group is None]
        parallel_groups: dict[int, list[Any]] = {}

        for step in self.steps:
            if step.parallel_group is not None:
                if step.parallel_group not in parallel_groups:
                    parallel_groups[step.parallel_group] = []
                parallel_groups[step.parallel_group].append(step)

        # Execute sequential steps first
        for step in sequential_steps:
            success, result, error = await self._execute_step(step, context)

            if success:
                context[step.output_key] = result
                steps_executed.append(step.output_key)
            else:
                steps_skipped.append(step.output_key)

            if error:
                errors[step.output_key] = error

        # Execute parallel groups
        for group_id in sorted(parallel_groups.keys()):
            group_steps = parallel_groups[group_id]

            self.logger.info(f"Executing parallel group {group_id} with {len(group_steps)} steps")

            # Execute all steps in group concurrently
            tasks = [
                self._execute_step(step, context)
                for step in group_steps
            ]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Process results
            for step, result in zip(group_steps, results):
                if isinstance(result, BaseException):
                    errors[step.output_key] = str(result)
                    steps_skipped.append(step.output_key)
                else:
                    success, value, error = result
                    if success:
                        context[step.output_key] = value
                        steps_executed.append(step.output_key)
                    else:
                        steps_skipped.append(step.output_key)

                    if error:
                        errors[step.output_key] = error

        # Determine overall success
        success = len(errors) == 0

        return ChainResult(
            success=success,
            context=context,
            steps_executed=steps_executed,
            steps_skipped=steps_skipped,
            errors=errors
        )

    async def execute_partial(
        self,
        initial_context: Dict[str, Any],
        until_step: str
    ) -> ChainResult:
        """
        Execute chain until a specific step.

        Args:
            initial_context: Initial context values
            until_step: Stop after this step (by output_key)

        Returns:
            ChainResult with partial execution
        """
        # Find step index
        stop_index = None
        for i, step in enumerate(self.steps):
            if step.output_key == until_step:
                stop_index = i
                break

        if stop_index is None:
            raise ValueError(f"Step not found: {until_step}")

        # Save original steps
        original_steps = self.steps
        self.steps = self.steps[:stop_index + 1]

        try:
            result = await self.execute(initial_context)
            return result
        finally:
            self.steps = original_steps

    def clear(self) -> None:
        """Clear all steps from chain."""
        self.steps.clear()
        self.logger.debug("Cleared chain steps")

    def get_steps(self) -> List[Dict[str, Any]]:
        """
        Get list of steps in chain.

        Returns:
            List of step information
        """
        return [
            {
                "tool_name": step.tool_name,
                "output_key": step.output_key,
                "input_mapping": step.input_mapping,
                "parallel_group": step.parallel_group,
                "has_condition": step.condition is not None
            }
            for step in self.steps
        ]

    def visualize(self) -> str:
        """
        Generate text visualization of chain.

        Returns:
            ASCII diagram of chain
        """
        lines = ["Tool Chain:"]
        lines.append("=" * 50)

        current_group = None

        for i, step in enumerate(self.steps):
            # Handle parallel groups
            if step.parallel_group is not None:
                if step.parallel_group != current_group:
                    lines.append(f"\n[Parallel Group {step.parallel_group}]")
                    current_group = step.parallel_group
                prefix = "  ├─"
            else:
                if current_group is not None:
                    lines.append("")  # Blank line after parallel group
                    current_group = None
                prefix = f"{i+1}."

            # Format inputs
            inputs = ", ".join(f"{k}←{v}" for k, v in step.input_mapping.items())

            # Build line
            line = f"{prefix} {step.tool_name}({inputs}) → {step.output_key}"

            if step.condition:
                line += " [conditional]"

            lines.append(line)

        return "\n".join(lines)


class ChainBuilder:
    """
    Fluent builder for creating tool chains.

    Provides a more intuitive API for chain construction.

    Example:
        >>> chain = (ChainBuilder(executor)
        ...     .step("search", {"query": "input"}, "results")
        ...     .step("summarize", {"text": "results"}, "summary")
        ...     .parallel([
        ...         ("translate_en", {"text": "summary"}, "english"),
        ...         ("translate_es", {"text": "summary"}, "spanish")
        ...     ])
        ...     .build())
    """

    def __init__(self, tool_executor: Callable):
        """
        Initialize chain builder.

        Args:
            tool_executor: Tool execution function
        """
        self.chain = ToolChain(tool_executor)

    def step(
        self,
        tool_name: str,
        input_mapping: Dict[str, str],
        output_key: str,
        **kwargs
    ) -> "ChainBuilder":
        """Add a step. See ToolChain.add_step for details."""
        self.chain.add_step(tool_name, input_mapping, output_key, **kwargs)
        return self

    def parallel(
        self,
        steps: List[tuple[str, Dict[str, str], str]],
        parallel_group: Optional[int] = None
    ) -> "ChainBuilder":
        """Add parallel steps. See ToolChain.add_parallel_steps for details."""
        self.chain.add_parallel_steps(steps, parallel_group)
        return self

    def conditional(
        self,
        condition: Callable[[Dict[str, Any]], bool],
        tool_name: str,
        input_mapping: Dict[str, str],
        output_key: str
    ) -> "ChainBuilder":
        """Add a conditional step."""
        self.chain.add_step(
            tool_name,
            input_mapping,
            output_key,
            condition=condition
        )
        return self

    def build(self) -> ToolChain:
        """
        Build and return the chain.

        Returns:
            Constructed ToolChain
        """
        return self.chain
