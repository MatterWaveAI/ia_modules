"""ParallelStep — runs child steps concurrently.

Used for fan-out patterns: all voters at once, all debaters at once,
all workers at once, etc. Each child step receives the same input data.
Results are merged into a dict keyed by child step name.

Example:
    voters = ParallelStep("all_voters", {
        "steps": [voter_step_1, voter_step_2, voter_step_3]
    })
    result = await voters.run({"topic": "Should we merge?"})
    # result = {
    #     "voter_1": {"result": "approve", ...},
    #     "voter_2": {"result": "reject", ...},
    #     "voter_3": {"result": "approve", ...},
    # }
"""

import asyncio
import logging
from typing import Any, Dict, List

from ia_modules.pipeline.core import Step

logger = logging.getLogger(__name__)


class ParallelStep(Step):
    """Runs multiple child steps in parallel and merges results.

    Config keys:
        steps (list[Step]): Child steps to run concurrently.
    """

    def __init__(self, name: str, config: Dict[str, Any]):
        super().__init__(name, config)
        self._steps: List[Step] = config["steps"]

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Run all child steps in parallel, return merged results."""
        # Inject services into child steps
        for step in self._steps:
            step.services = self.services

        tasks = [step.execute_with_error_handling(data) for step in self._steps]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        merged: Dict[str, Any] = {}
        for step, result in zip(self._steps, results):
            if isinstance(result, Exception):
                logger.warning("Parallel child '%s' failed: %s", step.name, result)
                merged[step.name] = {"error": str(result), "step_error": True}
            else:
                merged[step.name] = result

        return merged
