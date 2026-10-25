"""Planning Agent - Creates execution plans using the Planning pattern"""

from typing import Dict, Any, Optional
from ia_modules.pipeline.core import PipelineStep


class PlanningAgentStep(PipelineStep):
    """
    Agent that creates detailed execution plans.
    Uses the Planning agentic pattern to decompose goals.
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.role = config.get("role", "Planning Agent")

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Generate execution plan for the task"""

        # Get task and context
        task = data.get("task", "")
        iteration = data.get("iteration", 0)
        previous_feedback = data.get("feedback", None)
        strategy_adjustments = data.get("strategy_adjustments", [])

        # Build plan prompt
        constraints_text = ""
        if previous_feedback:
            constraints_text = f"\nPrevious feedback to address:\n{previous_feedback}"

        if strategy_adjustments:
            adjustments = "\n".join(f"- {adj}" for adj in strategy_adjustments)
            constraints_text += f"\n\nStrategy adjustments from metacognition:\n{adjustments}"

        f"""You are a Planning Agent. Break down this task into 3-5 actionable steps.

Task: {task}

Iteration: {iteration + 1}
{constraints_text}

For each step provide:
1. A clear subgoal
2. Reasoning for why this step is needed
3. Estimated duration (in minutes)
4. Dependencies on previous steps
5. Success criteria

Return your plan as a structured breakdown."""

        # Simulate LLM planning (in real implementation, call LLM service)
        plan = {
            "goal": task,
            "iteration": iteration + 1,
            "total_steps": 4,
            "estimated_total_time": 60,
            "steps": [
                {
                    "step_number": 1,
                    "subgoal": "Research and gather information",
                    "reasoning": "Need foundation knowledge before proceeding",
                    "estimated_duration": 15,
                    "dependencies": [],
                    "success_criteria": ["Key concepts identified", "Resources collected"]
                },
                {
                    "step_number": 2,
                    "subgoal": "Analyze and structure findings",
                    "reasoning": "Organization improves output quality",
                    "estimated_duration": 20,
                    "dependencies": [1],
                    "success_criteria": ["Logical structure created", "Key points outlined"]
                },
                {
                    "step_number": 3,
                    "subgoal": "Execute core task",
                    "reasoning": "Main work happens here",
                    "estimated_duration": 20,
                    "dependencies": [2],
                    "success_criteria": ["Task completed", "Output generated"]
                },
                {
                    "step_number": 4,
                    "subgoal": "Review and refine",
                    "reasoning": "Quality assurance step",
                    "estimated_duration": 5,
                    "dependencies": [3],
                    "success_criteria": ["Output polished", "Quality criteria met"]
                }
            ],
            "agent": "Planning Agent",
            "pattern_used": "planning"
        }

        # Add to execution history
        if "execution_history" not in data:
            data["execution_history"] = []

        data["execution_history"].append({
            "agent": "planner",
            "iteration": iteration + 1,
            "action": "created_plan",
            "output": plan
        })

        return {
            **data,
            "plan": plan,
            "current_step": "planning",
            "iteration": iteration + 1
        }
