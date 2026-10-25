"""
Publish Content Step for Loop Pipeline

Publishes the final approved content.
"""

from typing import Dict, Any
from ia_modules.pipeline.core import Step
import uuid


class PublishContentStep(Step):
    """Publish the final approved content"""

    async def run(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Publish the final content
        
        Args:
            data: Input data containing:
                - draft: str - The final approved draft
                - quality_score: float - Final quality score
        
        Returns:
            Dict with:
                - published_url: str - URL where content was published
                - final_draft: str - The published content
                - publication_id: str - Unique publication ID
        """
        draft = data.get('draft', '')
        quality_score = data.get('quality_score', 0)
        
        # Generate a unique publication ID
        publication_id = str(uuid.uuid4())[:8]
        
        # Simulate publishing
        published_url = f"https://example.com/content/{publication_id}"
        
        # Add publication metadata to final draft
        final_draft = draft + f"\n\n[Published with quality score: {quality_score}]"
        
        return {
            "published_url": published_url,
            "final_draft": final_draft,
            "publication_id": publication_id,
            "quality_score": quality_score
        }
