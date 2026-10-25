"""
Quality Assessment Step for HITL Pipeline Testing
Determines if human intervention is required based on quality metrics
"""
from typing import Dict, Any
from ia_modules.pipeline.core import Step


class QualityAssessmentStep(Step):
    """
    Assesses the quality of processed content and determines if human review is needed
    """
    
    async def run(self, data: Dict[str, Any]) -> Any:
        quality_score = data.get("quality_score", 0.5)
        confidence = data.get("confidence", 0.5)
        issues_detected = data.get("issues_detected", [])
        
        confidence_threshold = self.config.get("confidence_threshold", 0.85)
        self.config.get("escalation_enabled", True)
        
        # Determine if human review is required
        requires_human_review = False
        review_reasons = []
        
        if quality_score < 0.8:
            requires_human_review = True
            review_reasons.append(f"Quality score ({quality_score:.2f}) below threshold (0.8)")
            
        if confidence < confidence_threshold:
            requires_human_review = True
            review_reasons.append(f"Confidence ({confidence:.2f}) below threshold ({confidence_threshold})")
            
        if len(issues_detected) > 0:
            requires_human_review = True
            review_reasons.append(f"Issues detected: {', '.join(issues_detected)}")
            
        # Determine review urgency
        urgency = "low"
        if quality_score < 0.7 or confidence < 0.75:
            urgency = "high"
        elif quality_score < 0.8 or confidence < 0.8:
            urgency = "medium"
            
        # Assessment summary
        assessment = {
            "requires_human_review": requires_human_review,
            "review_reasons": review_reasons,
            "urgency": urgency,
            "automated_approval": not requires_human_review,
            "quality_metrics": {
                "quality_score": quality_score,
                "confidence": confidence,
                "issues_count": len(issues_detected)
            },
            "recommendation": "approve" if not requires_human_review else "review_required"
        }
        
        # Pass through original data with assessment
        return {
            **data,
            "quality_assessment": assessment,
            "requires_human_review": requires_human_review,
            "review_reasons": review_reasons,
            "urgency": urgency,
            "assessment_timestamp": "2025-09-25T10:01:00Z"
        }