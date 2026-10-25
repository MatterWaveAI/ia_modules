"""Basic dialog control rails."""
from typing import Any, Dict, Optional, List
from ..base import BaseGuardrail
from ..models import RailResult, RailAction, RailType


class ContextLengthRail(BaseGuardrail):
    """
    Enforce maximum conversation context length.

    Prevents excessively long conversation histories that may exceed
    token limits or degrade performance.
    """

    def __init__(self, config, max_turns: int = 10, max_tokens: int = 4000):
        """
        Initialize context length rail.

        Args:
            config: Rail configuration
            max_turns: Maximum number of conversation turns
            max_tokens: Maximum estimated tokens (rough estimate: 4 chars = 1 token)
        """
        super().__init__(config)
        self.max_turns = max_turns
        self.max_tokens = max_tokens

    async def check(self, content: Any, context: Optional[Dict[str, Any]] = None) -> RailResult:
        """Check conversation context length."""
        context = context or {}
        conversation_history = context.get("conversation_history", [])

        # Check turn count
        if len(conversation_history) > self.max_turns:
            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.DIALOG,
                action=RailAction.WARN,
                original_content=content,
                triggered=True,
                reason=f"Conversation exceeded {self.max_turns} turns",
                confidence=1.0,
                metadata={
                    "turn_count": len(conversation_history),
                    "max_turns": self.max_turns,
                    "recommendation": "Consider summarizing or truncating history"
                }
            )

        # Estimate token count (rough: 4 characters ≈ 1 token)
        total_chars = sum(len(str(msg.get("content", ""))) for msg in conversation_history)
        total_chars += len(str(content))
        estimated_tokens = total_chars // 4

        if estimated_tokens > self.max_tokens:
            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.DIALOG,
                action=RailAction.WARN,
                original_content=content,
                triggered=True,
                reason=f"Estimated tokens ({estimated_tokens}) exceeded limit ({self.max_tokens})",
                confidence=0.7,
                metadata={
                    "estimated_tokens": estimated_tokens,
                    "max_tokens": self.max_tokens,
                    "recommendation": "Truncate conversation history"
                }
            )

        return RailResult(
            rail_id=self.config.id,
            rail_type=RailType.DIALOG,
            action=RailAction.ALLOW,
            original_content=content,
            triggered=False,
            metadata={
                "turn_count": len(conversation_history),
                "estimated_tokens": estimated_tokens
            }
        )


class TopicAdherenceRail(BaseGuardrail):
    """
    Ensure conversation stays on topic.

    Detects and warns about topic drift in conversations.
    """

    def __init__(self, config, allowed_topics: Optional[List[str]] = None,
                 strict_mode: bool = False):
        """
        Initialize topic adherence rail.

        Args:
            config: Rail configuration
            allowed_topics: List of allowed topic keywords
            strict_mode: If True, BLOCK off-topic messages; if False, WARN only
        """
        super().__init__(config)
        self.allowed_topics = [t.lower() for t in (allowed_topics or [])]
        self.strict_mode = strict_mode

    async def check(self, content: Any, context: Optional[Dict[str, Any]] = None) -> RailResult:
        """Check if message is on topic."""
        if not self.allowed_topics:
            # No topic restrictions
            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.DIALOG,
                action=RailAction.ALLOW,
                original_content=content,
                triggered=False
            )

        if not isinstance(content, str):
            content = str(content)

        content_lower = content.lower()

        # Check if any allowed topic appears in content
        matched_topics = [topic for topic in self.allowed_topics if topic in content_lower]

        if not matched_topics:
            action = RailAction.BLOCK if self.strict_mode else RailAction.WARN
            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.DIALOG,
                action=action,
                original_content=content,
                triggered=True,
                reason=f"Message appears off-topic. Allowed topics: {', '.join(self.allowed_topics)}",
                confidence=0.6,
                metadata={
                    "allowed_topics": self.allowed_topics,
                    "matched_topics": [],
                    "strict_mode": self.strict_mode
                }
            )

        return RailResult(
            rail_id=self.config.id,
            rail_type=RailType.DIALOG,
            action=RailAction.ALLOW,
            original_content=content,
            triggered=False,
            metadata={
                "matched_topics": matched_topics
            }
        )


class ConversationFlowRail(BaseGuardrail):
    """
    Control conversation flow patterns.

    Detects repetitive patterns or conversation loops.
    """

    def __init__(self, config, max_repetitions: int = 3):
        """
        Initialize conversation flow rail.

        Args:
            config: Rail configuration
            max_repetitions: Maximum allowed repetitions of similar messages
        """
        super().__init__(config)
        self.max_repetitions = max_repetitions

    async def check(self, content: Any, context: Optional[Dict[str, Any]] = None) -> RailResult:
        """Check for conversation loops or repetition."""
        context = context or {}
        conversation_history = context.get("conversation_history", [])

        if not isinstance(content, str):
            content = str(content)

        # Count similar messages in recent history (last 10 messages)
        recent_history = conversation_history[-10:] if len(conversation_history) > 10 else conversation_history
        similar_count = 0

        for msg in recent_history:
            msg_content = str(msg.get("content", ""))
            # Simple similarity check: same words
            if self._calculate_similarity(content, msg_content) > 0.7:
                similar_count += 1

        if similar_count >= self.max_repetitions:
            return RailResult(
                rail_id=self.config.id,
                rail_type=RailType.DIALOG,
                action=RailAction.WARN,
                original_content=content,
                triggered=True,
                reason=f"Repetitive pattern detected ({similar_count} similar messages)",
                confidence=0.8,
                metadata={
                    "similar_count": similar_count,
                    "max_repetitions": self.max_repetitions,
                    "recommendation": "User may be stuck in a loop"
                }
            )

        return RailResult(
            rail_id=self.config.id,
            rail_type=RailType.DIALOG,
            action=RailAction.ALLOW,
            original_content=content,
            triggered=False,
            metadata={"similar_count": similar_count}
        )

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate simple word overlap similarity."""
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())

        if not words1 or not words2:
            return 0.0

        intersection = words1.intersection(words2)
        union = words1.union(words2)

        return len(intersection) / len(union) if union else 0.0
