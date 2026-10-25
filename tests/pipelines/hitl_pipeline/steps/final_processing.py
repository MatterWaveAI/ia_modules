"""
Final Processing Step for HITL Pipeline Testing
Compiles final output with complete audit trail
"""
from typing import Dict, Any
from ia_modules.pipeline.core import Step


class FinalProcessingStep(Step):
    """
    Final processing step that compiles results and creates audit trail
    """
    
    async def run(self, data: Dict[str, Any]) -> Any:
        output_format = self.config.get("output_format", "json")
        include_audit_trail = self.config.get("include_audit_trail", True)
        
        # Extract final content (could be enhanced or original)
        final_content = data.get("final_enhanced_content") or data.get("processed_content", "")
        
        # Compile processing summary
        processing_summary = {
            "processing_id": data.get("processing_id"),
            "original_content": data.get("original_content"),
            "final_content": final_content,
            "quality_metrics": {
                "initial_quality_score": data.get("quality_score"),
                "initial_confidence": data.get("confidence"),
                "final_status": "processed"
            }
        }
        
        # Compile HITL interaction summary  
        hitl_summary = {
            "human_review_occurred": "human_feedback" in data,
            "enhancement_occurred": "enhancement_history" in data,
            "collaborative_decision_occurred": "collaborative_decision" in data,
            "total_human_interactions": 0
        }
        
        # Count human interactions
        if "human_feedback" in data:
            hitl_summary["total_human_interactions"] += 1
            hitl_summary["review_decision"] = data.get("decision")
            hitl_summary["human_feedback"] = data.get("human_feedback")
            
        if "enhancement_history" in data:
            enhancement_history = data.get("enhancement_history", [])
            hitl_summary["total_human_interactions"] += len(enhancement_history)
            hitl_summary["enhancement_iterations"] = len(enhancement_history)
            
        if "collaborative_decision" in data:
            hitl_summary["total_human_interactions"] += len(data["collaborative_decision"].get("stakeholder_votes", []))
            hitl_summary["collaborative_decision"] = data.get("collaborative_decision")
        
        # Create audit trail if requested
        audit_trail = []
        if include_audit_trail:
            audit_trail = [
                {
                    "step": "initial_processing",
                    "timestamp": "2025-09-25T10:00:00Z",
                    "action": "automated_processing",
                    "result": "content_processed"
                },
                {
                    "step": "quality_assessment", 
                    "timestamp": "2025-09-25T10:01:00Z",
                    "action": "quality_check",
                    "result": f"requires_human_review: {data.get('requires_human_review', False)}"
                }
            ]
            
            if "human_feedback" in data:
                audit_trail.append({
                    "step": "human_review",
                    "timestamp": data.get("review_timestamp", "2025-09-25T10:02:00Z"),
                    "action": "human_review",
                    "actor": "human_reviewer",
                    "result": f"decision: {data.get('decision')}"
                })
                
            if "enhancement_history" in data:
                for i, enhancement in enumerate(data.get("enhancement_history", [])):
                    audit_trail.append({
                        "step": "manual_enhancement",
                        "timestamp": enhancement.get("timestamp", "2025-09-25T10:03:00Z"),
                        "action": f"enhancement_iteration_{enhancement.get('iteration', i+1)}",
                        "actor": "human_enhancer", 
                        "result": "content_enhanced"
                    })
                    
            if "collaborative_decision" in data:
                collab_decision = data.get("collaborative_decision", {})
                audit_trail.append({
                    "step": "collaborative_decision",
                    "timestamp": collab_decision.get("decision_timestamp", "2025-09-25T10:04:00Z"),
                    "action": "stakeholder_voting",
                    "actors": collab_decision.get("voting_results", {}).get("total_stakeholders", 0),
                    "result": f"final_decision: {collab_decision.get('final_decision')}"
                })
                
            audit_trail.append({
                "step": "final_processing",
                "timestamp": "2025-09-25T10:05:00Z", 
                "action": "compilation",
                "result": "pipeline_complete"
            })
        
        # Compile final output
        final_output = {
            "status": "complete",
            "processing_summary": processing_summary,
            "hitl_summary": hitl_summary,
            "output_format": output_format,
            "completion_timestamp": "2025-09-25T10:05:00Z",
            "pipeline_metadata": {
                "name": "Human-in-the-Loop Test Pipeline",
                "version": "1.0.0",
                "execution_id": data.get("processing_id")
            }
        }
        
        if include_audit_trail:
            final_output["audit_trail"] = audit_trail
            
        # Include all processed data for testing
        final_output["complete_data_trace"] = {
            key: value for key, value in data.items() 
            if not key.startswith("_")  # Exclude internal fields
        }
        
        return final_output