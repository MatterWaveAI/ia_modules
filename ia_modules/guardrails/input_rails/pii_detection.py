"""PII detection and redaction guardrail."""
from typing import Any, Dict, Optional
import re
from ..base import BaseGuardrail
from ..models import RailResult, RailAction, RailType


class PIIDetectionRail(BaseGuardrail):
    """
    Detect and optionally redact Personally Identifiable Information (PII).

    Detects:
    - Email addresses
    - Phone numbers
    - Social Security Numbers
    - Credit card numbers
    - IP addresses
    """

    PII_PATTERNS = {
        "email": r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b',
        "phone": r'\b\d{3}[-.]?\d{3}[-.]?\d{4}\b',
        "ssn": r'\b\d{3}-\d{2}-\d{4}\b',
        "credit_card": r'\b\d{4}[-\s]?\d{4}[-\s]?\d{4}[-\s]?\d{4}\b',
        "ip_address": r'\b(?:\d{1,3}\.){3}\d{1,3}\b',
    }

    def __init__(self, config, redact: bool = True):
        """
        Initialize PII detection rail.

        Args:
            config: Rail configuration
            redact: If True, redact PII instead of blocking
        """
        super().__init__(config)
        self.redact = redact

    async def check(self, content: Any, context: Optional[Dict[str, Any]] = None) -> RailResult:
        """Check for PII in content."""
        if not isinstance(content, str):
            content = str(content)

        detected_pii = []
        modified_content = content

        for pii_type, pattern in self.PII_PATTERNS.items():
            matches = re.findall(pattern, content)

            if matches:
                detected_pii.append({
                    "type": pii_type,
                    "count": len(matches)
                })

                if self.redact:
                    # Redact PII
                    modified_content = re.sub(
                        pattern,
                        f"[{pii_type.upper()}_REDACTED]",
                        modified_content
                    )

        if detected_pii:
            action = RailAction.MODIFY if self.redact else RailAction.BLOCK

            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.INPUT,
                action=action,
                original_content=content,
                modified_content=modified_content if self.redact else None,
                triggered=True,
                reason=f"PII detected: {', '.join(p['type'] for p in detected_pii)}",
                confidence=0.95,
                metadata={"detected_pii": detected_pii}
            )

        return RailResult(
            rail_id=self.config.id,
            rail_type=RailType.INPUT,
            action=RailAction.ALLOW,
            original_content=content,
            triggered=False
        )
