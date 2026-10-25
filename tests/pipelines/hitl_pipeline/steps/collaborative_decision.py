"""
Collaborative Decision Step for HITL Pipeline Testing  
Demonstrates multi-stakeholder approval pattern
"""
import uuid
from typing import Dict, Any
from ia_modules.pipeline.core import Step


class CollaborativeDecisionStep(Step):
    """
    Handles multi-stakeholder collaborative decision making
    Demonstrates the real-time collaboration HITL pattern
    """
    
    async def run(self, data: Dict[str, Any]) -> Any:
        stakeholders = self.config.get("stakeholders", ["reviewer1", "reviewer2", "manager"])
        decision_type = self.config.get("decision_type", "majority") # all, majority, any
        timeout_hours = self.config.get("timeout_hours", 24)
        self.config.get("voting_options", ["approve", "reject", "request_changes"])
        
        decision_id = str(uuid.uuid4())
        
        # Extract content for collaborative review
        data.get("processed_content", "")
        data.get("quality_assessment", {})
        human_feedback = data.get("human_feedback", "")
        
        # Create collaborative decision UI schema
        ui_schema = {
            "type": "collaborative_decision",
            "title": "Team Decision Required",
            "description": f"Escalated content requires team decision. Previous feedback: {human_feedback}",
            "stakeholders": stakeholders,
            "decision_type": decision_type,
            "fields": [
                {
                    "name": "vote",
                    "type": "radio",
                    "label": "Your Decision",
                    "options": [
                        {"value": "approve", "label": "Approve - Ready for final processing"},
                        {"value": "reject", "label": "Reject - Needs major rework"},
                        {"value": "request_changes", "label": "Request Changes - Minor modifications needed"}
                    ],
                    "required": True
                },
                {
                    "name": "reasoning",
                    "type": "textarea", 
                    "label": "Decision Reasoning",
                    "placeholder": "Explain your decision and provide specific feedback...",
                    "required": True
                },
                {
                    "name": "urgency",
                    "type": "select",
                    "label": "Urgency Level",
                    "options": [
                        {"value": "low", "label": "Low - Can wait"},
                        {"value": "medium", "label": "Medium - Normal priority"},
                        {"value": "high", "label": "High - Time sensitive"},
                        {"value": "critical", "label": "Critical - Immediate action needed"}
                    ]
                },
                {
                    "name": "stakeholder_id",
                    "type": "hidden",
                    "value": "{{current_user_id}}"
                }
            ]
        }
        
        # For testing - simulate stakeholder responses
        simulated_votes = []
        quality_score = data.get("quality_score", 0.5)
        
        for i, stakeholder in enumerate(stakeholders):
            # Simulate different stakeholder perspectives
            if quality_score > 0.8:
                vote = "approve"
                reasoning = f"{stakeholder}: Quality looks good, I approve."
            elif quality_score > 0.7 and i % 2 == 0:
                vote = "approve" 
                reasoning = f"{stakeholder}: Acceptable quality, approved with minor reservations."
            elif quality_score > 0.6:
                vote = "request_changes"
                reasoning = f"{stakeholder}: Some improvements needed before approval."
            else:
                vote = "reject"
                reasoning = f"{stakeholder}: Quality too low, requires significant rework."
                
            simulated_votes.append({
                "stakeholder": stakeholder,
                "vote": vote,
                "reasoning": reasoning,
                "urgency": "medium",
                "timestamp": "2025-09-25T10:04:00Z"
            })
        
        # Calculate decision result based on voting
        approve_count = sum(1 for v in simulated_votes if v["vote"] == "approve")
        reject_count = sum(1 for v in simulated_votes if v["vote"] == "reject")
        change_count = sum(1 for v in simulated_votes if v["vote"] == "request_changes")
        
        total_votes = len(simulated_votes)
        
        if decision_type == "all":
            final_decision = "approve" if approve_count == total_votes else "rejected"
        elif decision_type == "majority":
            if approve_count > total_votes / 2:
                final_decision = "approve"
            elif reject_count > total_votes / 2:
                final_decision = "reject"
            else:
                final_decision = "request_changes"
        else:  # any
            if approve_count > 0:
                final_decision = "approve"
            else:
                final_decision = "reject"
        
        # Compile decision summary
        decision_summary = {
            "decision_id": decision_id,
            "final_decision": final_decision,
            "voting_results": {
                "approve": approve_count,
                "reject": reject_count, 
                "request_changes": change_count,
                "total_stakeholders": total_votes
            },
            "stakeholder_votes": simulated_votes,
            "decision_type": decision_type,
            "decision_timestamp": "2025-09-25T10:04:00Z",
            "consensus_level": approve_count / total_votes if total_votes > 0 else 0
        }
        
        return {
            "status": "collaborative_decision_complete",
            "decision_id": decision_id, 
            "ui_schema": ui_schema,
            "timeout_hours": timeout_hours,
            "collaborative_decision": decision_summary,
            "final_decision": final_decision,
            "stakeholder_feedback": [v["reasoning"] for v in simulated_votes],
            # Pass through original data
            **data,
            "decision_complete": True
        }