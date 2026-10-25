"""
Simple HITL Pipeline Steps for Getting Started
"""

from typing import Dict, Any
from ia_modules.pipeline.core import Step


class PrepareDataStep(Step):
    """First step: prepare data for human review"""

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Prepare some data for review"""
        message = self.config.get('message', 'Preparing data')

        return {
            "prepared_data": {
                "content": "Sample content that needs human review",
                "timestamp": "2024-01-01T10:00:00Z",
                "quality_score": 0.75
            },
            "status": "prepared",
            "message": message
        }


class SimpleHumanReviewStep(Step):
    """Second step: pause for human review"""

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Pause execution and wait for human input.

        Returns special status to signal HITL interaction needed.
        """
        prompt = self.config.get('prompt', 'Please review and provide input')
        timeout_seconds = self.config.get('timeout_seconds', 300)

        # Build simple UI schema for the review
        ui_schema = {
            "type": "form",
            "title": "Review Required",
            "fields": [
                {
                    "name": "decision",
                    "type": "radio",
                    "label": "Your Decision",
                    "options": [
                        {"value": "approve", "label": "Approve"},
                        {"value": "reject", "label": "Reject"}
                    ],
                    "required": True
                },
                {
                    "name": "comments",
                    "type": "textarea",
                    "label": "Comments",
                    "placeholder": "Optional feedback...",
                    "required": False
                }
            ]
        }

        # Return special status to pause execution and wait for human input
        # The pipeline runner will detect this and create a HITL interaction
        return {
            "status": "human_input_required",
            "prompt": prompt,
            "ui_schema": ui_schema,
            "timeout_seconds": timeout_seconds,
            "channels": self.config.get('channels', ['web']),  # Which channels to notify: web, email, slack, discord, sms
            "assigned_users": self.config.get('assigned_users', []),  # Which users to assign this to
            "prepared_data": data.get("prepared_data")  # Pass through relevant data
        }


class FinalizeStep(Step):
    """Third step: finalize based on human decision"""

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Finalize the pipeline"""
        message = self.config.get('message', 'Finalizing')

        human_decision = data.get('human_decision', 'unknown')
        human_comments = data.get('human_comments', '')

        return {
            "status": "completed",
            "message": message,
            "human_decision": human_decision,
            "human_comments": human_comments,
            "final_result": f"Pipeline completed with decision: {human_decision}"
        }
