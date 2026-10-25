"""Basic output filtering rails."""
from typing import Any, Dict, Optional
from ..base import BaseGuardrail
from ..models import RailResult, RailAction, RailType


class ToxicOutputFilterRail(BaseGuardrail):
    """
    Filter toxic content in LLM outputs.

    Prevents the LLM from generating harmful, toxic, or inappropriate responses.
    """

    TOXIC_KEYWORDS = [
        "hate", "violent", "offensive", "inappropriate",
        "kill", "harm", "attack", "threat"
    ]

    async def check(self, content: Any, context: Optional[Dict[str, Any]] = None) -> RailResult:
        """Check output for toxic content."""
        if not isinstance(content, str):
            content = str(content)

        content_lower = content.lower()

        # Check for toxic keywords
        toxic_count = sum(1 for keyword in self.TOXIC_KEYWORDS if keyword in content_lower)

        if toxic_count > 0:
            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.OUTPUT,
                action=RailAction.BLOCK,
                original_content=content,
                triggered=True,
                reason=f"Toxic content in output ({toxic_count} toxic keywords)",
                confidence=min(1.0, toxic_count / 3)
            )

        return RailResult(
            rail_id=self.config.id,
            rail_type=RailType.OUTPUT,
            action=RailAction.ALLOW,
            original_content=content,
            triggered=False
        )


class DisclaimerRail(BaseGuardrail):
    """
    Add disclaimers to certain types of responses.

    Useful for medical, legal, or financial advice.
    """

    def __init__(self, config, disclaimer_text: Optional[str] = None):
        """
        Initialize disclaimer rail.

        Args:
            config: Rail configuration
            disclaimer_text: Custom disclaimer to add
        """
        super().__init__(config)
        self.disclaimer = disclaimer_text or (
            "Disclaimer: This information is for general purposes only and "
            "should not be considered professional advice."
        )

    async def check(self, content: Any, context: Optional[Dict[str, Any]] = None) -> RailResult:
        """Add disclaimer if needed."""
        if not isinstance(content, str):
            content = str(content)

        # Keywords that trigger disclaimer
        trigger_keywords = ["medical", "legal", "financial", "investment", "diagnosis", "treatment"]

        content_lower = content.lower()
        needs_disclaimer = any(keyword in content_lower for keyword in trigger_keywords)

        if needs_disclaimer:
            modified = f"{content}\n\n{self.disclaimer}"

            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.OUTPUT,
                action=RailAction.MODIFY,
                original_content=content,
                modified_content=modified,
                triggered=True,
                reason="Added disclaimer to potentially sensitive advice",
                confidence=1.0
            )

        return RailResult(
            rail_id=self.config.id,
            rail_type=RailType.OUTPUT,
            action=RailAction.ALLOW,
            original_content=content,
            triggered=False
        )


class LengthLimitRail(BaseGuardrail):
    """
    Enforce maximum output length.

    Prevents excessively long responses that may be costly or slow.
    """

    def __init__(self, config, max_length: int = 1000):
        """
        Initialize length limit rail.

        Args:
            config: Rail configuration
            max_length: Maximum allowed length in characters
        """
        super().__init__(config)
        self.max_length = max_length

    async def check(self, content: Any, context: Optional[Dict[str, Any]] = None) -> RailResult:
        """Check output length."""
        if not isinstance(content, str):
            content = str(content)

        if len(content) > self.max_length:
            # Truncate with ellipsis
            truncated = content[:self.max_length - 3] + "..."

            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.OUTPUT,
                action=RailAction.MODIFY,
                original_content=content,
                modified_content=truncated,
                triggered=True,
                reason=f"Output exceeded {self.max_length} characters",
                confidence=1.0,
                metadata={
                    "original_length": len(content),
                    "truncated_length": len(truncated)
                }
            )

        return RailResult(
            rail_id=self.config.id,
            rail_type=RailType.OUTPUT,
            action=RailAction.ALLOW,
            original_content=content,
            triggered=False,
            metadata={"length": len(content)}
        )
