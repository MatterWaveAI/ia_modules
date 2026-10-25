"""Toxicity detection guardrail."""
from typing import Any, Dict, Optional
from ..base import BaseGuardrail
from ..models import RailResult, RailAction, RailType


class ToxicityDetectionRail(BaseGuardrail):
    """
    Detect toxic, harmful, or inappropriate input.

    Categories:
    - Hate speech
    - Violence
    - Sexual content
    - Harassment
    - Self-harm
    """

    TOXIC_KEYWORDS = [
        # Hate speech indicators
        "hate", "racist", "sexist", "bigot",
        # Violence
        "kill", "murder", "harm", "attack",
        # Harassment
        "threat", "harass", "stalk",
    ]

    async def check(self, content: Any, context: Optional[Dict[str, Any]] = None) -> RailResult:
        """Check for toxic content."""
        if not isinstance(content, str):
            content = str(content)

        content_lower = content.lower()

        # Simple keyword detection (in production, use ML model like Perspective API)
        toxic_score = sum(
            1 for keyword in self.TOXIC_KEYWORDS
            if keyword in content_lower
        ) / len(self.TOXIC_KEYWORDS)

        if toxic_score > 0.1:  # More than 10% keywords match
            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.INPUT,
                action=RailAction.BLOCK,
                original_content=content,
                triggered=True,
                reason="Toxic content detected",
                confidence=min(1.0, toxic_score * 2),
                metadata={"toxicity_score": toxic_score}
            )

        return RailResult(
            rail_id=self.config.id,
            rail_type=RailType.INPUT,
            action=RailAction.ALLOW,
            original_content=content,
            triggered=False
        )
