"""
Draft Content Step for Loop Pipeline

Generates initial draft content and tracks revision count.
"""

from typing import Dict, Any
from ia_modules.pipeline.core import Step


class DraftContentStep(Step):
    """Generate or revise draft content"""

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Generate draft content based on topic or revise based on feedback
        
        Args:
            data: Input data containing:
                - topic: str - The topic to write about
                - feedback: str (optional) - Feedback from previous review
                - revision_count: int (optional) - Current revision count
        
        Returns:
            Dict with:
                - draft: str - The generated/revised draft
                - revision_count: int - Updated revision count
        """
        topic = data.get('topic', 'general topic')
        feedback = data.get('feedback', '')
        revision_count = data.get('revision_count', 0)
        
        # Increment revision count
        revision_count += 1
        
        # Generate draft based on whether this is first draft or revision
        if revision_count == 1:
            # First draft
            draft = f"Draft content about {topic}. This is the initial version."
        else:
            # Revision based on feedback
            draft = f"REVISED (v{revision_count}): Content about {topic}. "
            if feedback:
                draft += f"Improvements made based on: {feedback}"
            else:
                draft += "Content has been improved and expanded."
        
        return {
            "draft": draft,
            "revision_count": revision_count
        }
