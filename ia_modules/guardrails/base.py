"""Base guardrail implementation."""
from typing import Any, Optional, Dict
from abc import ABC, abstractmethod
from .models import RailResult, GuardrailConfig


class BaseGuardrail(ABC):
    """
    Base class for all guardrails.

    Guardrails can:
    - Inspect content (input, output, retrieval, etc.)
    - Allow, block, modify, or warn about content
    - Log violations and metrics
    """

    def __init__(self, config: GuardrailConfig):
        """
        Initialize guardrail.

        Args:
            config: Guardrail configuration
        """
        self.config = config
        self.execution_count = 0
        self.trigger_count = 0

    @abstractmethod
    async def check(self, content: Any, context: Optional[Dict[str, Any]] = None) -> RailResult:
        """
        Check content against guardrail.

        Args:
            content: Content to check
            context: Additional context

        Returns:
            Rail result with action to take
        """
        pass

    async def execute(self, content: Any, context: Optional[Dict[str, Any]] = None) -> RailResult:
        """
        Execute guardrail check with metrics tracking.

        Args:
            content: Content to check
            context: Additional context

        Returns:
            Rail result
        """
        self.execution_count += 1

        result = await self.check(content, context)

        if result.triggered:
            self.trigger_count += 1

        return result

    def get_stats(self) -> Dict[str, Any]:
        """Get guardrail statistics."""
        return {
            "rail_id": self.config.id,
            "rail_name": self.config.name,
            "rail_type": self.config.type.value,
            "executions": self.execution_count,
            "triggers": self.trigger_count,
            "trigger_rate": self.trigger_count / max(1, self.execution_count),
            "enabled": self.config.enabled
        }
