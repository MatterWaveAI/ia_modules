"""
Agent orchestrator with graph-based execution.

Manages multi-agent workflows with explicit control flow, conditional
branching, and feedback loops.

Runs Step instances (from ia_modules.pipeline.core) in a directed graph
with shared StateManager. Steps communicate through shared memory, not
through step I/O like Pipeline does.

Backward-compatible with BaseAgent — legacy agents are wrapped automatically.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Callable, Any
import logging
import time

from .state import StateManager

logger = logging.getLogger(__name__)


@dataclass
class Edge:
    """
    Represents a transition between steps in the workflow graph.

    Attributes:
        to: Target step ID
        condition: Optional async condition function(state) -> bool
        metadata: Additional edge configuration
    """
    to: str
    condition: Optional[Callable] = None
    metadata: Optional[Dict[str, Any]] = None

    def __post_init__(self):
        if self.metadata is None:
            self.metadata = {}


class AgentOrchestrator:
    """
    Orchestrates multi-agent workflows with graph-based execution.

    Runs Step instances in a directed graph with shared StateManager.
    Steps communicate through shared memory (StateManager), not through
    step I/O like Pipeline does.

    Accepts both Step (ia_modules.pipeline.core) and legacy BaseAgent
    instances. BaseAgent instances are wrapped automatically.

    Features:
    - Graph-based step sequencing
    - Conditional branching based on state
    - Feedback loops with automatic iteration tracking
    - Parallel step execution
    - Cycle detection

    Example:
        >>> state = StateManager(thread_id="user-123")
        >>> orch = AgentOrchestrator(state)
        >>>
        >>> # Register steps
        >>> orch.add_step("planner", planner_step)
        >>> orch.add_step("coder", coder_step)
        >>> orch.add_step("critic", critic_step)
        >>>
        >>> # Build workflow: planner → coder → critic
        >>> orch.add_edge("planner", "coder")
        >>> orch.add_edge("coder", "critic")
        >>>
        >>> # Add feedback loop: critic → coder (if not approved)
        >>> orch.add_feedback_loop("coder", "critic", max_iterations=3)
        >>>
        >>> # Execute
        >>> result = await orch.run("planner", {"task": "Build API"})
    """

    def __init__(self, state_manager: StateManager, services=None):
        """
        Initialize orchestrator.

        Args:
            state_manager: Centralized state for step communication
            services: Optional ServiceRegistry for dependency injection into Steps
        """
        self.state = state_manager
        self.steps: Dict[str, Any] = {}  # Step or wrapped BaseAgent
        self.graph: Dict[str, List[Edge]] = {}
        self.logger = logging.getLogger(f"Orchestrator.{state_manager.thread_id}")

        # ServiceRegistry — if provided, register StateManager on it
        self.services = services
        if services is not None:
            if not services.has('state_manager'):
                services.register('state_manager', state_manager)

        # Execution hooks for monitoring/tracking
        self.on_step_start: List[Callable] = []
        self.on_step_complete: List[Callable] = []
        self.on_step_error: List[Callable] = []

        # Aliases for backward compat — collaboration_service uses these directly
        self.on_agent_start = self.on_step_start
        self.on_agent_complete = self.on_step_complete
        self.on_agent_error = self.on_step_error

    @property
    def agents(self) -> Dict[str, Any]:
        """Backward compat alias for self.steps."""
        return self.steps

    def add_step(self, step_id: str, step) -> None:
        """
        Register a Step in the workflow.

        Args:
            step_id: Unique identifier for this step
            step: Step instance (from ia_modules.pipeline.core)
        """
        # Inject services so step gets access to StateManager
        if self.services is not None:
            step.services = self.services

        self.steps[step_id] = step
        if step_id not in self.graph:
            self.graph[step_id] = []

        self.logger.debug("Added step: %s (%s)", step_id, type(step).__name__)

    def add_agent(self, agent_id: str, agent) -> None:
        """
        Register an agent or step in the workflow.

        Accepts both Step and legacy BaseAgent instances. BaseAgent
        instances are wrapped in a _LegacyAgentWrapper automatically.

        Args:
            agent_id: Unique identifier
            agent: Step or BaseAgent instance
        """
        # Check if it's a Step (duck-type: has run() method and is not BaseAgent)
        from .core import BaseAgent
        from ia_modules.pipeline.core import Step

        if isinstance(agent, Step):
            self.add_step(agent_id, agent)
        elif isinstance(agent, BaseAgent):
            # Wrap legacy BaseAgent as a Step
            wrapper = _LegacyAgentWrapper(agent_id, agent)
            if self.services is not None:
                wrapper.services = self.services
            self.steps[agent_id] = wrapper
            if agent_id not in self.graph:
                self.graph[agent_id] = []
            self.logger.debug("Added legacy agent (wrapped): %s (%s)", agent_id, agent.role.name)
        else:
            # Unknown type — store as-is for maximum flexibility
            self.steps[agent_id] = agent
            if agent_id not in self.graph:
                self.graph[agent_id] = []
            self.logger.debug("Added agent: %s (%s)", agent_id, type(agent).__name__)

    def add_hook(self, event: str, callback: Callable) -> None:
        """
        Add execution hook for monitoring step lifecycle.

        Args:
            event: Hook event type. Accepts both step_* and agent_* prefixes:
                   'step_start' / 'agent_start'
                   'step_complete' / 'agent_complete'
                   'step_error' / 'agent_error'
            callback: Async callback function:
                     - start: callback(step_id: str, input_data: Dict)
                     - complete: callback(step_id: str, output_data: Dict, duration: float)
                     - error: callback(step_id: str, error: Exception)
        """
        hook_map = {
            'step_start': self.on_step_start,
            'step_complete': self.on_step_complete,
            'step_error': self.on_step_error,
            'agent_start': self.on_step_start,
            'agent_complete': self.on_step_complete,
            'agent_error': self.on_step_error,
        }
        target = hook_map.get(event)
        if target is None:
            raise ValueError(f"Unknown hook event: {event}. Valid: step_start, step_complete, step_error")
        target.append(callback)
        self.logger.debug("Added %s hook", event)

    def add_edge(self, from_step: str, to_step: str,
                 condition: Optional[Callable] = None,
                 metadata: Optional[Dict[str, Any]] = None) -> None:
        """
        Add transition between steps.

        Args:
            from_step: Source step ID
            to_step: Target step ID
            condition: Optional async function(state) -> bool
            metadata: Additional edge configuration
        """
        if from_step not in self.graph:
            self.graph[from_step] = []

        self.graph[from_step].append(
            Edge(to=to_step, condition=condition, metadata=metadata or {})
        )

        self.logger.debug("Added edge: %s → %s", from_step, to_step)

    def add_feedback_loop(self, worker_step: str, critic_step: str,
                         max_iterations: int = 3,
                         next_step: Optional[str] = None) -> Callable:
        """
        Add feedback loop between worker and critic steps.

        Creates edges:
        1. worker → critic (always)
        2. critic → worker (if not approved and under max iterations)
        3. critic → next_step (if approved or max iterations reached)

        Args:
            worker_step: Step that produces work
            critic_step: Step that reviews work
            max_iterations: Maximum feedback iterations
            next_step: Next step after loop completes

        Returns:
            Condition function for "loop complete"
        """
        # Worker → Critic (always)
        self.add_edge(worker_step, critic_step)

        iteration_key = f"{worker_step}_iterations"

        # Critic → Worker (if not approved and under max iterations)
        async def needs_revision(state: StateManager) -> bool:
            approved = await state.get("approved", False)
            iterations = await state.get(iteration_key, 0)

            if not approved and iterations < max_iterations:
                await state.set(iteration_key, iterations + 1)
                self.logger.info("Feedback loop iteration %d/%d", iterations + 1, max_iterations)
                return True

            return False

        self.add_edge(critic_step, worker_step, condition=needs_revision,
                     metadata={"type": "feedback_loop", "max_iterations": max_iterations})

        # Critic → Next (if approved or max iterations)
        async def is_complete(state: StateManager) -> bool:
            approved = await state.get("approved", False)
            iterations = await state.get(iteration_key, 0)
            complete = approved or iterations >= max_iterations

            if complete:
                self.logger.info("Feedback loop complete (approved=%s, iterations=%d)", approved, iterations)

            return complete

        if next_step:
            self.add_edge(critic_step, next_step, condition=is_complete)

        return is_complete

    async def run(self, start_step: str, input_data: Optional[Dict[str, Any]] = None,
                  max_steps: int = 100) -> Dict[str, Any]:
        """
        Execute workflow starting from start_step.

        Steps are executed by calling their run() method with a snapshot
        of the current shared state as input. Steps communicate by
        reading/writing the shared StateManager.

        Args:
            start_step: Step ID to start workflow
            input_data: Initial input data (merged into state)
            max_steps: Maximum execution steps (prevents infinite loops)

        Returns:
            Final state snapshot
        """
        if start_step not in self.steps:
            raise ValueError(f"Unknown start step: {start_step}")

        # Initialize state with input
        if input_data:
            await self.state.update(input_data)
        self.logger.info("Starting workflow from %s", start_step)

        reliability = self.services.get('reliability_metrics') if self.services else None
        workflow_success = True

        current = start_step
        steps_taken = 0
        execution_path = []

        while current and steps_taken < max_steps:
            steps_taken += 1
            execution_path.append(current)

            self.logger.info("Step %d: Executing %s", steps_taken, current)

            step = self.steps[current]

            # Fire start hooks
            for hook in self.on_step_start:
                try:
                    await hook(current, input_data or {})
                except Exception as e:
                    self.logger.warning("Hook failed on step_start: %s", e)

            try:
                t0 = time.time()

                # Get state snapshot as step input
                snapshot = await self.state.snapshot()

                # Execute: Step uses run(), wrapped BaseAgent uses run() too (via wrapper)
                result = await step.run(snapshot)

                duration = time.time() - t0
                self.logger.debug("%s returned: %s", current, result)

                # Fire complete hooks
                for hook in self.on_step_complete:
                    try:
                        await hook(current, result, duration)
                    except Exception as e:
                        self.logger.warning("Hook failed on step_complete: %s", e)

                if reliability:
                    await reliability.record_step(agent=current, success=True)

            except Exception as e:
                self.logger.error("Step %s failed: %s", current, e)
                workflow_success = False

                # Fire error hooks
                for hook in self.on_step_error:
                    try:
                        await hook(current, e)
                    except Exception as hook_error:
                        self.logger.warning("Hook failed on step_error: %s", hook_error)

                if reliability:
                    await reliability.record_step(agent=current, success=False)

                await self.state.set("error", str(e))
                await self.state.set("failed_step", current)
                raise

            # Find next step
            next_step = await self._get_next_step(current)

            if next_step:
                self.logger.debug("Next step: %s", next_step)
            else:
                self.logger.info("Workflow complete (no more steps)")

            current = next_step  # type: ignore[assignment]

        if steps_taken >= max_steps:
            raise RuntimeError(
                f"Max steps ({max_steps}) exceeded. Possible infinite loop. "
                f"Path: {execution_path}"
            )

        # Save execution metadata
        await self.state.set("execution_path", execution_path)
        await self.state.set("total_steps", steps_taken)

        if reliability:
            await reliability.record_workflow(
                workflow_id=self.state.thread_id,
                steps=steps_taken,
                retries=0,
                success=workflow_success,
            )

        self.logger.info(
            "Workflow complete in %d steps: %s",
            steps_taken, " → ".join(execution_path)
        )

        return await self.state.snapshot()

    async def _get_next_step(self, current_step: str) -> Optional[str]:
        """Determine next step based on edges and conditions."""
        edges = self.graph.get(current_step, [])

        for edge in edges:
            if edge.condition is None:
                return edge.to

            try:
                if await edge.condition(self.state):
                    return edge.to
            except Exception as e:
                self.logger.error(
                    "Condition evaluation failed for edge %s→%s: %s",
                    current_step, edge.to, e
                )
                continue

        return None

    def visualize(self) -> str:
        """Generate Mermaid diagram of workflow."""
        lines = ["graph TD"]

        for from_id, edges in self.graph.items():
            step = self.steps.get(from_id)
            from_label = self._step_label(from_id, step)

            for edge in edges:
                to_step = self.steps.get(edge.to)
                to_label = self._step_label(edge.to, to_step)

                if edge.condition:
                    condition_name = edge.condition.__name__
                    lines.append(f"    {from_id}[{from_label}] -->|{condition_name}| {edge.to}[{to_label}]")
                else:
                    lines.append(f"    {from_id}[{from_label}] --> {edge.to}[{to_label}]")

        return "\n".join(lines)

    @staticmethod
    def _step_label(step_id: str, step) -> str:
        """Get display label for a step."""
        if step is None:
            return step_id
        # Legacy BaseAgent wrapper
        if isinstance(step, _LegacyAgentWrapper):
            return step._agent.role.name
        # Step with name
        if hasattr(step, 'name'):
            return step.name
        return step_id

    def get_agent_stats(self) -> Dict[str, Any]:
        """Get orchestrator statistics."""
        return {
            "num_steps": len(self.steps),
            "num_edges": sum(len(edges) for edges in self.graph.values()),
            "steps": list(self.steps.keys()),
            "state_keys": len(self.state._state),
            "state_versions": self.state.version_count(),
            # Backward compat aliases
            "num_agents": len(self.steps),
            "agents": list(self.steps.keys()),
        }

    def __repr__(self) -> str:
        return (
            f"<AgentOrchestrator(steps={len(self.steps)}, "
            f"edges={sum(len(e) for e in self.graph.values())})>"
        )


class _LegacyAgentWrapper:
    """Wraps a BaseAgent as a Step-like object for backward compatibility.

    Delegates run() to agent.execute() so the orchestrator can treat
    everything uniformly. Has the same interface as Step (name, config,
    services, run) without actually inheriting from Step to avoid
    circular imports.
    """

    def __init__(self, name: str, agent):
        self.name = name
        self.config: Dict[str, Any] = {}
        self.services = None
        self._agent = agent
        self.logger = logging.getLogger(f"LegacyWrapper.{name}")

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Delegate to BaseAgent.execute()."""
        return await self._agent.execute(data)

    async def execute(self, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Backward compat — collaboration_service calls agent.execute() directly."""
        return await self._agent.execute(input_data)

    async def execute_with_error_handling(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Simple pass-through — legacy agents handle their own errors."""
        return await self.run(data)

    @property
    def role(self):
        """Backward compat — expose wrapped agent's role."""
        return self._agent.role
