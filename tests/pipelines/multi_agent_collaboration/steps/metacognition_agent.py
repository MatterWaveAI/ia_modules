"""Metacognition Agent - Analyzes collaboration effectiveness"""

from typing import Dict, Any, Optional
from ia_modules.pipeline.core import PipelineStep


class MetacognitionAgentStep(PipelineStep):
    """
    Agent that monitors the collaboration process and suggests strategy adjustments.
    Uses the Metacognition pattern to analyze execution patterns.
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.role = config.get("role", "Metacognition Agent")

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze collaboration effectiveness and suggest adjustments"""

        execution_history = data.get("execution_history", [])
        iteration = data.get("iteration", 1)
        quality_score = data.get("quality_score", 0.0)

        # Build execution trace
        execution_trace = []
        for entry in execution_history:
            if entry["iteration"] == iteration:
                execution_trace.append({
                    "agent": entry["agent"],
                    "action": entry["action"],
                    "success": True  # Simplified
                })

        # Analyze patterns
        metacognition = {
            "agent": "Metacognition Agent",
            "pattern_used": "metacognition",
            "iteration": iteration,
            "execution_trace": execution_trace,
            "performance_assessment": "",
            "patterns_detected": [],
            "collaboration_health": {},
            "strategy_adjustments": []
        }

        # Calculate collaboration metrics
        agent_participation = {}
        for entry in execution_trace:
            agent = entry["agent"]
            agent_participation[agent] = agent_participation.get(agent, 0) + 1

        metacognition["collaboration_health"] = {
            "iterations_completed": iteration,
            "quality_trend": "improving" if quality_score > 0.7 else "needs improvement",
            "agent_participation": agent_participation,
            "communication_flow": "healthy" if len(agent_participation) >= 3 else "limited"
        }

        # Performance assessment
        if quality_score >= 0.85:
            metacognition["performance_assessment"] = "Excellent - collaboration is highly effective"
        elif quality_score >= 0.7:
            metacognition["performance_assessment"] = "Good - minor refinements needed"
        else:
            metacognition["performance_assessment"] = "Below target - significant improvements required"

        # Detect patterns
        if iteration == 1:
            metacognition["patterns_detected"] = [
                "Initial planning phase - baseline established",
                "All agents participating actively",
                "Feedback loop established"
            ]
        elif quality_score < data.get("previous_quality_score", 0):
            metacognition["patterns_detected"] = [
                "Quality regression detected",
                "Strategy adjustment may be counterproductive",
                "Consider reverting to previous approach"
            ]
        else:
            improvement = quality_score - data.get("previous_quality_score", quality_score)
            metacognition["patterns_detected"] = [
                f"Quality improved by {improvement:.2f}",
                "Iterative refinement working effectively",
                "Agent collaboration synchronized"
            ]

        # Strategy adjustments
        if quality_score < 0.7:
            metacognition["strategy_adjustments"] = [
                "Increase detail in planning phase",
                "Add validation checkpoints in execution",
                "Focus critic feedback on specific weak areas",
                "Allocate more time to research step"
            ]
        elif quality_score < 0.85:
            metacognition["strategy_adjustments"] = [
                "Fine-tune execution based on critique",
                "Optimize process efficiency",
                "Enhance output presentation"
            ]
        else:
            metacognition["strategy_adjustments"] = [
                "Maintain current high quality",
                "Minor polish only"
            ]

        metacognition["analysis"] = f"""Collaboration Analysis - Iteration {iteration}

Performance: {metacognition['performance_assessment']}
Quality Score: {quality_score:.2f}

Patterns Identified:
{chr(10).join(f'• {p}' for p in metacognition['patterns_detected'])}

Collaboration Health:
• Iterations: {iteration}
• Trend: {metacognition['collaboration_health']['quality_trend']}
• Communication: {metacognition['collaboration_health']['communication_flow']}

Recommended Adjustments:
{chr(10).join(f'{i+1}. {adj}' for i, adj in enumerate(metacognition['strategy_adjustments']))}
"""

        # Add to execution history
        data["execution_history"].append({
            "agent": "metacognition",
            "iteration": iteration,
            "action": "analyzed_collaboration",
            "output": metacognition
        })

        return {
            **data,
            "metacognition": metacognition,
            "current_step": "metacognition",
            "strategy_adjustments": metacognition["strategy_adjustments"],
            "collaboration_health": metacognition["collaboration_health"],
            "previous_quality_score": quality_score
        }
