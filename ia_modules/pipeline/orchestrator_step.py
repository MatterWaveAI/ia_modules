"""OrchestratorStep — runs an entire orchestrator pattern as a single pipeline Step.

The pipeline sees this as one atomic step: input in, output out. Inside,
it creates a StateManager, wires child steps into an orchestrator graph,
runs it, and returns the final state as step output.

Pipeline infrastructure applies to the whole orchestrator as one unit:
- Checkpointed as one step
- Retried as one unit
- NDJSON logged as one step lifecycle
- HITL can pause before/after the orchestrator runs

Example:
    async def build_consensus_graph(orch, state, data):
        # Create and wire steps...
        orch.add_step("voters", parallel_voters)
        orch.add_step("aggregator", aggregator_step)
        orch.add_edge("voters", "aggregator")
        await state.set("topic", data["topic"])

    step = OrchestratorStep("consensus", {
        "build_graph": build_consensus_graph,
        "start_step": "voters",
        "output_keys": ["consensus_reached", "votes", "final_agreement"],
    })

This means orchestrator patterns can nest. A hierarchical pattern's leader
could delegate a subtask that itself runs a consensus pattern — it's Steps
all the way down.
"""

import logging
from typing import Any, Callable, Dict, List

from ia_modules.agents.orchestrator import AgentOrchestrator
from ia_modules.agents.state import StateManager
from ia_modules.pipeline.core import Step
from ia_modules.pipeline.services import ServiceRegistry

logger = logging.getLogger(__name__)


class OrchestratorStep(Step):
    """Wraps an orchestrator graph as a single pipeline step.

    Config keys:
        build_graph (callable): async fn(orch, state, data) that registers
            steps and wires edges on the orchestrator.
        start_step (str): Which step to start the orchestrator from.
        max_steps (int): Orchestrator step limit. Default 100.
        output_keys (list[str]): State keys to include in step output.
            If empty/None, returns full state snapshot.
        thread_id (str): Optional thread ID for StateManager.
            Defaults to execution_id from data or step name.
    """

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self._build_graph: Callable = config["build_graph"]
        self._start_step: str = config["start_step"]
        self._max_steps: int = config.get("max_steps", 100)
        self._output_keys: List[str] = config.get("output_keys") or []

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Create orchestrator, build graph, run, return result."""
        thread_id = (
            self.config.get("thread_id")
            or data.get("_execution_id")
            or self.name
        )
        state = StateManager(thread_id=thread_id)
        services = ServiceRegistry()

        orch = AgentOrchestrator(state, services)

        # Let the builder wire the graph
        await self._build_graph(orch, state, data)

        # Run the orchestrator
        final_state = await orch.run(
            self._start_step,
            max_steps=self._max_steps,
        )

        # Extract output — specific keys or full snapshot
        if self._output_keys:
            return {k: final_state.get(k) for k in self._output_keys}
        return final_state
