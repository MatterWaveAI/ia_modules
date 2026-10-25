"""
Iterative Refinement HITL Pattern

Allows humans to progressively enhance and refine automated results
through multiple iterations.
"""

from typing import Dict, Any
from ia_modules.pipeline.core import Step


class IterativeRefinementStep(Step):
    """
    Progressive enhancement pattern - human iteratively improves results.

    Configuration:
        max_iterations: Maximum number of refinement cycles (default: 3)
        prompt: Initial prompt for refinement
        auto_continue: If True, automatically continue to next iteration (default: False)

    Input data should contain:
        current_result: The result to refine
        iteration: Current iteration number (default: 1)
        refinement_history: List of previous refinements (optional)

    Output on refinement needed:
        status: "human_input_required"
        ui_schema: Form for refinement

    Output on completion:
        status: "refinement_complete"
        final_result: The refined result
        iterations_completed: Number of iterations performed
    """

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Execute iterative refinement step"""
        # Get configuration
        max_iterations = self.config.get('max_iterations', 3)
        prompt = self.config.get('prompt', 'Please refine the result')

        # Get current state
        iteration = data.get('iteration', 1)
        current_result = data.get('current_result', data)
        refinement_history = data.get('refinement_history', [])

        # Check if max iterations reached
        if iteration > max_iterations:
            self.logger.info(f"Max iterations ({max_iterations}) reached")
            return {
                "status": "refinement_complete",
                "final_result": current_result,
                "iterations_completed": iteration - 1,
                "refinement_history": refinement_history
            }

        # Build UI schema for refinement
        ui_schema = {
            "type": "form",
            "title": f"Iterative Refinement - Round {iteration}/{max_iterations}",
            "fields": [
                {
                    "name": "refined_result",
                    "type": "textarea",
                    "label": f"Refine Result (Iteration {iteration})",
                    "description": "Edit and improve the current result",
                    "default": str(current_result),
                    "required": True,
                    "rows": 10
                },
                {
                    "name": "refinement_notes",
                    "type": "textarea",
                    "label": "What changes did you make?",
                    "description": "Document your improvements for tracking",
                    "required": False,
                    "rows": 3
                },
                {
                    "name": "continue_refining",
                    "type": "checkbox",
                    "label": "Continue to next iteration?",
                    "description": f"Uncheck if you're satisfied with the result (or hit max at {max_iterations})",
                    "default": iteration < max_iterations
                }
            ]
        }

        # Return HITL request for refinement
        return {
            "status": "human_input_required",
            "prompt": f"{prompt} (Iteration {iteration}/{max_iterations})",
            "ui_schema": ui_schema,
            "iteration": iteration,
            "current_result": current_result,
            "refinement_history": refinement_history,
            "max_iterations": max_iterations
        }


class ProcessRefinementResponseStep(Step):
    """
    Process the human's refinement response and decide next action.

    This step should come after IterativeRefinementStep in the pipeline.
    It processes the human input and either continues refinement or completes.
    """

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Process refinement response"""
        # Get human input
        refined_result = data.get('refined_result')
        refinement_notes = data.get('refinement_notes', '')
        continue_refining = data.get('continue_refining', False)

        # Get context
        iteration = data.get('iteration', 1)
        refinement_history = data.get('refinement_history', [])
        max_iterations = data.get('max_iterations', 3)

        # Record this refinement
        refinement_record = {
            "iteration": iteration,
            "notes": refinement_notes,
            "result": refined_result
        }
        refinement_history.append(refinement_record)

        # Check if we should continue or finish
        if continue_refining and iteration < max_iterations:
            # Continue to next iteration
            return {
                "current_result": refined_result,
                "iteration": iteration + 1,
                "refinement_history": refinement_history,
                "status": "continue_refinement",
                "max_iterations": max_iterations
            }
        else:
            # Refinement complete
            return {
                "status": "refinement_complete",
                "final_result": refined_result,
                "iterations_completed": iteration,
                "refinement_history": refinement_history
            }
