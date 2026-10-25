"""
Human Review Step for HITL Pipeline Testing
Simulates pause-and-resume pattern where human input is required
"""
import uuid
from typing import Dict, Any
from ia_modules.pipeline.core import Step


class HumanReviewStep(Step):
    """
    Pauses pipeline execution for human review and approval
    Demonstrates the pause-and-resume HITL pattern
    """
    
    async def run(self, data: Dict[str, Any]) -> Any:
        interaction_id = str(uuid.uuid4())
        timeout_seconds = self.config.get("timeout_seconds", 300)
        
        # Extract content for review
        processed_content = data.get("processed_content", "")
        quality_assessment = data.get("quality_assessment", {})
        review_reasons = data.get("review_reasons", [])
        
        # Create UI schema for human interaction
        ui_schema = {
            "type": "review_approval",
            "title": "Content Review Required",
            "description": f"Please review the processed content. Issues: {', '.join(review_reasons)}",
            "fields": [
                {
                    "name": "decision",
                    "type": "radio",
                    "label": "Review Decision",
                    "options": [
                        {"value": "approve", "label": "Approve - Content is acceptable"},
                        {"value": "reject", "label": "Reject - Content needs rework"}, 
                        {"value": "request_enhancement", "label": "Request Enhancement - Needs improvement"},
                        {"value": "escalate", "label": "Escalate - Requires team decision"}
                    ],
                    "required": True
                },
                {
                    "name": "feedback",
                    "type": "textarea",
                    "label": "Review Comments",
                    "placeholder": "Provide specific feedback about the content...",
                    "required": False
                },
                {
                    "name": "suggested_changes",
                    "type": "textarea",
                    "label": "Suggested Improvements",
                    "placeholder": "Describe specific changes or improvements needed...",
                    "required": False
                },
                {
                    "name": "priority",
                    "type": "select",
                    "label": "Priority Level",
                    "options": [
                        {"value": "low", "label": "Low Priority"},
                        {"value": "medium", "label": "Medium Priority"},
                        {"value": "high", "label": "High Priority"},
                        {"value": "urgent", "label": "Urgent"}
                    ],
                    "default": "medium"
                },
                {
                    "name": "reviewer_name",
                    "type": "text",
                    "label": "Reviewer Name",
                    "required": True
                }
            ]
        }
        
        # For testing purposes, simulate human input based on quality
        # In real implementation, this would pause and wait for actual human input
        quality_score = data.get("quality_score", 0.5)
        
        # Simulate different human decisions based on quality
        if quality_score > 0.85:
            simulated_decision = "approve"
            simulated_feedback = "Content quality is good, approved for processing."
        elif quality_score > 0.75:
            simulated_decision = "request_enhancement"
            simulated_feedback = "Content is acceptable but could be improved."
        elif quality_score > 0.65:
            simulated_decision = "escalate"
            simulated_feedback = "Content quality concerns, escalating to team."
        else:
            simulated_decision = "reject"
            simulated_feedback = "Content quality too low, requires rework."
            
        # Return HITL interaction response
        return {
            "status": "human_input_required",
            "interaction_id": interaction_id,
            "ui_schema": ui_schema,
            "timeout_seconds": timeout_seconds,
            "review_data": {
                "content_to_review": processed_content,
                "quality_metrics": quality_assessment.get("quality_metrics", {}),
                "issues": review_reasons,
                "urgency": data.get("urgency", "medium")
            },
            # For testing - simulate human response
            "simulated_human_response": {
                "decision": simulated_decision,
                "feedback": simulated_feedback,
                "suggested_changes": "Improve clarity and add more detail." if simulated_decision == "request_enhancement" else "",
                "priority": "high" if quality_score < 0.7 else "medium",
                "reviewer_name": "Test Reviewer"
            },
            # Pass through original data
            **data,
            "decision": simulated_decision,
            "human_feedback": simulated_feedback,
            "review_timestamp": "2025-09-25T10:02:00Z"
        }