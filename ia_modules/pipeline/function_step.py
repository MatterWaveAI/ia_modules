"""FunctionStep — wraps an async callable as a pipeline/orchestrator Step.

Used for pure logic steps that don't need an LLM or subprocess:
vote tallying, data aggregation, synthesis, routing decisions, etc.

The function receives (data, step) where step is the FunctionStep instance,
giving access to read_state/write_state, services, config, etc.

Example:
    async def tally_votes(data, step):
        votes = await step.read_state("votes") or {}
        approve = sum(1 for v in votes.values() if v["vote"] == "approve")
        total = len(votes)
        reached = (approve / total) >= 0.5 if total else False
        await step.write_state("consensus_reached", reached)
        return {"approve": approve, "reject": total - approve, "reached": reached}

    step = FunctionStep("aggregator", {"fn": tally_votes})
"""

import logging
from typing import Any, Callable, Dict

from ia_modules.pipeline.core import Step

logger = logging.getLogger(__name__)


class FunctionStep(Step):
    """Step that executes an async function.

    Config keys:
        fn (callable): Async function with signature:
            async fn(data: dict, step: FunctionStep) -> dict
    """

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self._fn: Callable = config["fn"]

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the wrapped function."""
        return await self._fn(data, self)
