"""Execution Agent - Implements the plan using Tool Use pattern"""

from typing import Dict, Any, Optional
from ia_modules.pipeline.core import PipelineStep


class ExecutionAgentStep(PipelineStep):
    """
    Agent that executes the plan created by the planning agent.
    Uses the Tool Use pattern to select and apply appropriate tools.
    """

    def __init__(self, name: str, config: Optional[Dict[str, Any]] = None):
        super().__init__(name, config)
        self.role = config.get("role", "Execution Agent")

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute the plan steps"""

        plan = data.get("plan", {})
        task = data.get("task", "")
        iteration = data.get("iteration", 1)

        # Simulate tool selection and execution

        execution_result = {
            "agent": "Execution Agent",
            "pattern_used": "tool_use",
            "iteration": iteration,
            "steps_executed": [],
            "tools_used": [],
            "output": "",
            "metrics": {
                "total_duration": 0,
                "tools_invoked": 0,
                "success_rate": 1.0
            }
        }

        # Execute each step in the plan
        for step in plan.get("steps", []):
            # Determine which tools to use
            if "research" in step["subgoal"].lower():
                tools = ["research"]
            elif "analyze" in step["subgoal"].lower():
                tools = ["analyze", "synthesize"]
            elif "execute" in step["subgoal"].lower():
                tools = ["synthesize", "validate"]
            elif "review" in step["subgoal"].lower():
                tools = ["validate"]
            else:
                tools = ["research", "analyze"]

            step_result = {
                "step_number": step["step_number"],
                "subgoal": step["subgoal"],
                "tools_selected": tools,
                "reasoning": f"Selected {', '.join(tools)} to accomplish: {step['subgoal']}",
                "output": f"Completed: {step['subgoal']}",
                "duration": step["estimated_duration"],
                "success": True
            }

            execution_result["steps_executed"].append(step_result)
            execution_result["tools_used"].extend(tools)
            execution_result["metrics"]["total_duration"] += step["estimated_duration"]
            execution_result["metrics"]["tools_invoked"] += len(tools)

        # Generate summary output
        execution_result["output"] = f"""Task '{task}' executed successfully.

Completed {len(execution_result['steps_executed'])} steps across {iteration} iteration(s).
Tools used: {', '.join(set(execution_result['tools_used']))}
Total duration: {execution_result['metrics']['total_duration']} minutes

Results:
- Research completed with key findings identified
- Analysis structured and organized
- Core task executed with output generated
- Quality review performed
"""

        # Add to execution history
        data["execution_history"].append({
            "agent": "executor",
            "iteration": iteration,
            "action": "executed_plan",
            "output": execution_result
        })

        return {
            **data,
            "execution_result": execution_result,
            "current_step": "execution",
            "output": execution_result["output"]
        }
