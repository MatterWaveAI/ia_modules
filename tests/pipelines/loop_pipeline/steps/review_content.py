"""
Review Content Step for Loop Pipeline

Reviews draft content quality and determines if it needs revision.
"""

from typing import Dict, Any
from ia_modules.pipeline.core import Step


class ReviewContentStep(Step):
    """Review content quality and provide feedback"""

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Review draft content and determine if it's approved
        
        Args:
            data: Input data containing:
                - draft: str - The draft content to review
                - revision_count: int - Current revision count
        
        Returns:
            Dict with:
                - approved: bool - Whether content is approved
                - feedback: str - Feedback for improvement (if not approved)
                - quality_score: float - Quality score (0-100)
        """
        data.get('draft', '')
        revision_count = data.get('revision_count', 0)
        
        # Simulate quality assessment
        # Quality improves with revisions (but with diminishing returns)
        base_quality = 50
        revision_bonus = min(revision_count * 15, 40)  # Max 40 points from revisions
        quality_score = min(base_quality + revision_bonus, 95)
        
        # Approve if quality is high enough (>80) or max revisions reached
        max_revisions = self.config.get('max_revisions', 5)
        approved = quality_score >= 80 or revision_count >= max_revisions
        
        # Provide feedback if not approved
        if not approved:
            if quality_score < 60:
                feedback = "Content needs more detail and better structure."
            elif quality_score < 70:
                feedback = "Good progress, but needs more examples and clarity."
            else:
                feedback = "Almost there! Polish the language and add final touches."
        else:
            feedback = "Content approved for publication!"
        
        return {
            "approved": approved,
            "feedback": feedback,
            "quality_score": quality_score
        }
