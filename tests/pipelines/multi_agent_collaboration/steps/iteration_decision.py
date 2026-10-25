"""Iteration Decision Step - Decides whether to continue iterating"""

from typing import Dict, Any, Optional
from ia_modules.pipeline.core import PipelineStep


class IterationDecisionStep(PipelineStep):
    """
    Decides whether another iteration is needed based on quality score
    and max iterations limit.
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.quality_threshold = config.get("quality_threshold", 0.8)

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Decide whether to continue iterating"""

        quality_score = data.get("quality_score", 0.0)
        iteration = data.get("iteration", 1)
        max_iterations = data.get("max_iterations", 3)

        # Decision logic
        quality_met = quality_score >= self.quality_threshold
        max_reached = iteration >= max_iterations

        should_continue = not quality_met and not max_reached

        decision = {
            "current_iteration": iteration,
            "max_iterations": max_iterations,
            "quality_score": quality_score,
            "quality_threshold": self.quality_threshold,
            "quality_met": quality_met,
            "max_reached": max_reached,
            "should_continue": should_continue,
            "reason": ""
        }

        if quality_met:
            decision["reason"] = f"Quality threshold ({self.quality_threshold}) achieved with score {quality_score:.2f}"
        elif max_reached:
            decision["reason"] = f"Maximum iterations ({max_iterations}) reached"
        else:
            decision["reason"] = f"Continue improving (current: {quality_score:.2f}, target: {self.quality_threshold})"

        # Add to execution history
        data["execution_history"].append({
            "agent": "decision",
            "iteration": iteration,
            "action": "made_decision",
            "output": decision
        })

        return {
            **data,
            "should_continue": should_continue,
            "decision": decision,
            "current_step": "decision"
        }
