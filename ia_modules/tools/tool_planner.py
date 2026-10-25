"""
Tool planner for intelligent task decomposition and tool selection.

Analyzes tasks and creates execution plans using available tools.
"""

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set
from enum import Enum


class TaskComplexity(Enum):
    """Task complexity levels."""
    SIMPLE = "simple"  # Single tool execution
    MODERATE = "moderate"  # 2-3 tools, simple dependencies
    COMPLEX = "complex"  # Multiple tools, complex dependencies
    VERY_COMPLEX = "very_complex"  # Many tools, conditional logic


@dataclass
class Task:
    """
    Represents a high-level task to accomplish.

    Attributes:
        description: Human-readable task description
        requirements: Required capabilities or outputs
        constraints: Execution constraints (time, resources, etc.)
        context: Additional context information
    """
    description: str
    requirements: List[str] = field(default_factory=list)
    constraints: Dict[str, Any] = field(default_factory=dict)
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ExecutionPlan:
    """
    Plan for executing a task using tools.

    Attributes:
        task: Original task
        steps: Ordered list of tool executions
        estimated_time: Estimated execution time in seconds
        estimated_cost: Estimated cost (if applicable)
        complexity: Task complexity level
        alternatives: Alternative plans
        confidence: Confidence score (0-1)
    """
    task: Task
    steps: List[Dict[str, Any]] = field(default_factory=list)
    estimated_time: float = 0.0
    estimated_cost: float = 0.0
    complexity: TaskComplexity = TaskComplexity.SIMPLE
    alternatives: List["ExecutionPlan"] = field(default_factory=list)
    confidence: float = 1.0


@dataclass
class ToolMatch:
    """
    Represents a tool match for a requirement.

    Attributes:
        tool_name: Name of matched tool
        version: Tool version
        capability: Capability being matched
        confidence: Match confidence (0-1)
        reason: Why this tool was selected
    """
    tool_name: str
    version: str
    capability: str
    confidence: float
    reason: str


class ToolPlanner:
    """
    Plans tool execution for complex tasks.

    Features:
    - Task decomposition into subtasks
    - Tool selection based on capabilities
    - Dependency analysis
    - Multiple plan generation
    - Cost and time estimation
    - Plan optimization

    Example:
        >>> planner = ToolPlanner(tool_registry)
        >>>
        >>> task = Task(
        ...     description="Research and summarize AI trends",
        ...     requirements=["web_search", "summarization"]
        ... )
        >>>
        >>> plan = await planner.create_plan(task)
        >>> for step in plan.steps:
        ...     print(f"{step['tool_name']}: {step['description']}")
    """

    def __init__(self, tool_registry: Any):
        """
        Initialize tool planner.

        Args:
            tool_registry: Tool registry with capability indexing
        """
        self.tool_registry = tool_registry
        self.logger = logging.getLogger("ToolPlanner")

        # Capability to common tasks mapping
        self.capability_patterns = {
            "web_search": ["search", "find", "look up", "research"],
            "summarization": ["summarize", "condense", "brief"],
            "translation": ["translate", "convert language"],
            "calculation": ["calculate", "compute", "math"],
            "data_processing": ["process", "transform", "analyze"],
            "file_operations": ["read", "write", "save", "load"],
            "api_call": ["fetch", "request", "call api"],
        }

    def _analyze_task_complexity(self, task: Task) -> TaskComplexity:
        """
        Analyze task complexity.

        Args:
            task: Task to analyze

        Returns:
            Complexity level
        """
        # Count requirements
        num_requirements = len(task.requirements)

        # Check for conditional logic keywords
        description_lower = task.description.lower()
        conditional_keywords = ["if", "when", "unless", "depending", "either", "or"]
        has_conditionals = any(kw in description_lower for kw in conditional_keywords)

        # Estimate complexity
        if num_requirements <= 1 and not has_conditionals:
            return TaskComplexity.SIMPLE
        elif num_requirements <= 3 and not has_conditionals:
            return TaskComplexity.MODERATE
        elif num_requirements <= 5 or has_conditionals:
            return TaskComplexity.COMPLEX
        else:
            return TaskComplexity.VERY_COMPLEX

    def _extract_capabilities_from_description(self, description: str) -> List[str]:
        """
        Extract required capabilities from task description.

        Args:
            description: Task description

        Returns:
            List of capability names
        """
        capabilities = []
        description_lower = description.lower()

        for capability, patterns in self.capability_patterns.items():
            for pattern in patterns:
                if pattern in description_lower:
                    capabilities.append(capability)
                    break

        return capabilities

    def _match_tools_to_capability(
        self,
        capability: str,
        context: Optional[Dict[str, Any]] = None
    ) -> List[ToolMatch]:
        """
        Find tools that provide a capability.

        Args:
            capability: Capability name
            context: Optional context for matching

        Returns:
            List of tool matches, sorted by confidence
        """
        matches = []

        # Get tools with this capability
        if hasattr(self.tool_registry, 'find_by_capability'):
            tools = self.tool_registry.find_by_capability(capability)

            for tool_name, version, tool_def in tools:
                # Calculate confidence based on various factors
                confidence = 1.0

                # Reduce confidence if deprecated
                if hasattr(self.tool_registry, 'tools'):
                    if tool_name in self.tool_registry.tools:
                        if version in self.tool_registry.tools[tool_name]:
                            tool_version = self.tool_registry.tools[tool_name][version]
                            if tool_version.deprecated:
                                confidence *= 0.5

                match = ToolMatch(
                    tool_name=tool_name,
                    version=version,
                    capability=capability,
                    confidence=confidence,
                    reason=f"Provides {capability} capability"
                )
                matches.append(match)

        # Sort by confidence
        matches.sort(key=lambda m: m.confidence, reverse=True)

        return matches

    def _decompose_task(self, task: Task) -> List[Dict[str, Any]]:
        """
        Decompose task into subtasks.

        Args:
            task: Task to decompose

        Returns:
            List of subtask specifications
        """
        subtasks = []

        # Get requirements from explicit list or description
        requirements = task.requirements or self._extract_capabilities_from_description(
            task.description
        )

        # Create subtask for each requirement
        for i, capability in enumerate(requirements):
            subtasks.append({
                "index": i,
                "capability": capability,
                "description": f"Execute {capability}",
                "dependencies": [] if i == 0 else [i - 1],  # Simple sequential dependencies
            })

        return subtasks

    async def create_plan(
        self,
        task: Task,
        max_alternatives: int = 3
    ) -> ExecutionPlan:
        """
        Create execution plan for a task.

        Args:
            task: Task to plan
            max_alternatives: Maximum number of alternative plans

        Returns:
            Execution plan with selected tools
        """
        self.logger.info(f"Creating plan for: {task.description}")

        # Analyze complexity
        complexity = self._analyze_task_complexity(task)
        self.logger.debug(f"Task complexity: {complexity.value}")

        # Decompose into subtasks
        subtasks = self._decompose_task(task)
        self.logger.debug(f"Decomposed into {len(subtasks)} subtasks")

        # Match tools to subtasks
        steps = []
        total_confidence = 0.0

        for subtask in subtasks:
            capability = subtask["capability"]
            matches = self._match_tools_to_capability(capability, task.context)

            if not matches:
                self.logger.warning(f"No tools found for capability: {capability}")
                continue

            # Use best match
            best_match = matches[0]
            total_confidence += best_match.confidence

            step = {
                "tool_name": best_match.tool_name,
                "version": best_match.version,
                "capability": capability,
                "description": subtask["description"],
                "dependencies": subtask["dependencies"],
                "input_mapping": {},  # To be filled based on tool parameters
                "confidence": best_match.confidence
            }

            steps.append(step)

        # Calculate overall confidence
        avg_confidence = total_confidence / len(steps) if steps else 0.0

        # Estimate time and cost (simplified)
        estimated_time = len(steps) * 2.0  # 2 seconds per step
        estimated_cost = len(steps) * 0.01  # $0.01 per step

        plan = ExecutionPlan(
            task=task,
            steps=steps,
            estimated_time=estimated_time,
            estimated_cost=estimated_cost,
            complexity=complexity,
            confidence=avg_confidence
        )

        # Generate alternative plans if requested
        if max_alternatives > 0:
            plan.alternatives = await self._generate_alternative_plans(
                task,
                subtasks,
                max_alternatives
            )

        return plan

    async def _generate_alternative_plans(
        self,
        task: Task,
        subtasks: List[Dict[str, Any]],
        max_alternatives: int
    ) -> List[ExecutionPlan]:
        """
        Generate alternative execution plans.

        Args:
            task: Original task
            subtasks: Decomposed subtasks
            max_alternatives: Maximum alternatives to generate

        Returns:
            List of alternative plans
        """
        alternatives = []

        # For each subtask, try using alternative tools
        for alt_num in range(max_alternatives):
            steps = []
            total_confidence = 0.0

            for subtask in subtasks:
                capability = subtask["capability"]
                matches = self._match_tools_to_capability(capability, task.context)

                # Use different match for each alternative
                match_index = min(alt_num + 1, len(matches) - 1)
                if match_index < 0 or match_index >= len(matches):
                    break

                match = matches[match_index]
                total_confidence += match.confidence

                step = {
                    "tool_name": match.tool_name,
                    "version": match.version,
                    "capability": capability,
                    "description": subtask["description"],
                    "dependencies": subtask["dependencies"],
                    "input_mapping": {},
                    "confidence": match.confidence
                }

                steps.append(step)

            if len(steps) == len(subtasks):
                avg_confidence = total_confidence / len(steps)
                estimated_time = len(steps) * 2.0
                estimated_cost = len(steps) * 0.01

                alt_plan = ExecutionPlan(
                    task=task,
                    steps=steps,
                    estimated_time=estimated_time,
                    estimated_cost=estimated_cost,
                    complexity=self._analyze_task_complexity(task),
                    confidence=avg_confidence
                )
                alternatives.append(alt_plan)

        return alternatives

    def optimize_plan(self, plan: ExecutionPlan) -> ExecutionPlan:
        """
        Optimize execution plan.

        Args:
            plan: Plan to optimize

        Returns:
            Optimized plan
        """
        optimized_steps = []

        # Identify parallelizable steps
        dependency_map = {}
        for i, step in enumerate(plan.steps):
            dependency_map[i] = set(step.get("dependencies", []))

        # Assign parallel groups to independent steps
        parallel_group = 0
        assigned = set()

        for i, step in enumerate(plan.steps):
            if i in assigned:
                continue

            # Find all steps that can run with this one
            group = [i]
            deps_i = dependency_map[i]

            for j in range(i + 1, len(plan.steps)):
                if j in assigned:
                    continue

                deps_j = dependency_map[j]

                # Can run in parallel if no dependencies on each other
                if i not in deps_j and j not in deps_i:
                    # Also check transitive dependencies
                    can_parallel = True
                    for g in group:
                        if g in deps_j or j in dependency_map[g]:
                            can_parallel = False
                            break

                    if can_parallel:
                        group.append(j)

            # Assign parallel group
            for idx in group:
                step = plan.steps[idx].copy()
                if len(group) > 1:
                    step["parallel_group"] = parallel_group
                optimized_steps.append((idx, step))
                assigned.add(idx)

            if len(group) > 1:
                parallel_group += 1

        # Sort by original index
        optimized_steps.sort(key=lambda x: x[0])
        final_steps = [s[1] for s in optimized_steps]

        # Recalculate estimated time (parallel steps save time)
        groups = {}
        for step in final_steps:
            pg = step.get("parallel_group")
            if pg is not None:
                if pg not in groups:
                    groups[pg] = 0
                groups[pg] += 1

        # Time saved by parallelization
        parallel_time = (len(plan.steps) - sum(max(0, count - 1) for count in groups.values())) * 2.0

        return ExecutionPlan(
            task=plan.task,
            steps=final_steps,
            estimated_time=parallel_time,
            estimated_cost=plan.estimated_cost,
            complexity=plan.complexity,
            alternatives=plan.alternatives,
            confidence=plan.confidence
        )

    def validate_plan(self, plan: ExecutionPlan) -> tuple[bool, List[str]]:
        """
        Validate execution plan.

        Args:
            plan: Plan to validate

        Returns:
            Tuple of (is_valid, list_of_issues)
        """
        issues = []

        # Check for missing tools
        for step in plan.steps:
            tool = self.tool_registry.get_tool(step["tool_name"], step.get("version"))
            if tool is None:
                issues.append(f"Tool not found: {step['tool_name']}")

        # Check for circular dependencies
        dependency_map = {i: set(step.get("dependencies", [])) for i, step in enumerate(plan.steps)}

        def has_cycle(node: int, visited: Set[int], rec_stack: Set[int]) -> bool:
            visited.add(node)
            rec_stack.add(node)

            for dep in dependency_map.get(node, []):
                if dep not in visited:
                    if has_cycle(dep, visited, rec_stack):
                        return True
                elif dep in rec_stack:
                    return True

            rec_stack.remove(node)
            return False

        visited: set[int] = set()
        for i in range(len(plan.steps)):
            if i not in visited:
                if has_cycle(i, visited, set()):
                    issues.append("Circular dependencies detected")
                    break

        # Check for invalid dependencies (referencing non-existent steps)
        for i, step in enumerate(plan.steps):
            for dep in step.get("dependencies", []):
                if dep >= len(plan.steps) or dep < 0:
                    issues.append(f"Step {i} has invalid dependency: {dep}")

        return len(issues) == 0, issues

    def visualize_plan(self, plan: ExecutionPlan) -> str:
        """
        Generate text visualization of plan.

        Args:
            plan: Plan to visualize

        Returns:
            ASCII representation
        """
        lines = [
            f"Execution Plan: {plan.task.description}",
            "=" * 60,
            f"Complexity: {plan.complexity.value}",
            f"Estimated Time: {plan.estimated_time:.1f}s",
            f"Estimated Cost: ${plan.estimated_cost:.4f}",
            f"Confidence: {plan.confidence:.2%}",
            "",
            "Steps:"
        ]

        for i, step in enumerate(plan.steps):
            deps = step.get("dependencies", [])
            deps_str = f" (depends on: {deps})" if deps else ""
            pg = step.get("parallel_group")
            pg_str = f" [parallel group {pg}]" if pg is not None else ""

            lines.append(
                f"  {i}. {step['tool_name']} - {step['description']}"
                f"{deps_str}{pg_str}"
            )

        if plan.alternatives:
            lines.append(f"\n{len(plan.alternatives)} alternative plan(s) available")

        return "\n".join(lines)
