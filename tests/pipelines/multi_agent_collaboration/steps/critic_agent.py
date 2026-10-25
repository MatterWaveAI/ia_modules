"""Critic Agent - Provides feedback using Reflection pattern"""

from typing import Dict, Any, Optional
from ia_modules.pipeline.core import PipelineStep


class CriticAgentStep(PipelineStep):
    """
    Agent that critiques execution results and provides improvement feedback.
    Uses the Reflection pattern for self-critique.
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.role = config.get("role", "Reflection Agent")

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Critique the execution and provide feedback"""

        data.get("execution_result", {})
        data.get("output", "")
        iteration = data.get("iteration", 1)
        data.get("task", "")

        # Critique criteria

        # Simulate critique (in real implementation, use LLM)
        critique = {
            "agent": "Reflection Agent",
            "pattern_used": "reflection",
            "iteration": iteration,
            "criteria_scores": {},
            "strengths": [],
            "weaknesses": [],
            "improvements_suggested": [],
            "overall_quality": 0.0
        }

        # Score each criterion (simulate scoring based on iteration)
        base_score = 0.6 + (iteration * 0.1)  # Improves with iterations
        critique["criteria_scores"] = {
            "completeness": min(base_score + 0.1, 1.0),
            "quality": min(base_score, 1.0),
            "clarity": min(base_score + 0.05, 1.0),
            "efficiency": min(base_score - 0.05, 1.0),
            "accuracy": min(base_score + 0.15, 1.0)
        }

        critique["overall_quality"] = sum(critique["criteria_scores"].values()) / len(critique["criteria_scores"])

        # Generate feedback based on quality
        if critique["overall_quality"] < 0.7:
            critique["strengths"] = [
                "Basic structure is present",
                "Core requirements addressed"
            ]
            critique["weaknesses"] = [
                "Output lacks depth and detail",
                "Some criteria not fully met",
                "Could be more comprehensive"
            ]
            critique["improvements_suggested"] = [
                "Add more detailed analysis in step 2",
                "Expand on key findings with examples",
                "Improve clarity of final output",
                "Add validation checks"
            ]
        elif critique["overall_quality"] < 0.85:
            critique["strengths"] = [
                "Well-structured approach",
                "Good coverage of requirements",
                "Clear reasoning throughout"
            ]
            critique["weaknesses"] = [
                "Minor gaps in comprehensiveness",
                "Could optimize efficiency slightly"
            ]
            critique["improvements_suggested"] = [
                "Polish final presentation",
                "Add more specific examples",
                "Streamline process flow"
            ]
        else:
            critique["strengths"] = [
                "Excellent execution quality",
                "Comprehensive coverage",
                "Clear and well-structured",
                "Efficient process"
            ]
            critique["weaknesses"] = []
            critique["improvements_suggested"] = [
                "Minor refinements only"
            ]

        critique["feedback"] = f"""Quality Score: {critique['overall_quality']:.2f}

Strengths:
{chr(10).join(f'+ {s}' for s in critique['strengths'])}

{f"Areas for Improvement:{chr(10)}" + chr(10).join(f'- {w}' for w in critique['weaknesses']) if critique['weaknesses'] else 'No significant weaknesses identified.'}

Suggested Improvements:
{chr(10).join(f'{i+1}. {imp}' for i, imp in enumerate(critique['improvements_suggested']))}
"""

        # Add to execution history
        data["execution_history"].append({
            "agent": "critic",
            "iteration": iteration,
            "action": "critiqued_output",
            "output": critique
        })

        return {
            **data,
            "critique": critique,
            "current_step": "reflection",
            "quality_score": critique["overall_quality"],
            "feedback": critique["feedback"],
            "improvements": critique["improvements_suggested"]
        }
