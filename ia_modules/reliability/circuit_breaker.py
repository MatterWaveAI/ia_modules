"""
Circuit breaker pattern for agent reliability.

Automatically disables failing agents to prevent cascading failures
and allows them to recover gracefully.
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import logging


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"         # Normal operation, requests pass through
    OPEN = "open"             # Circuit tripped, requests blocked
    HALF_OPEN = "half_open"   # Testing if service recovered


@dataclass
class CircuitBreakerConfig:
    """
    Configuration for circuit breaker.

    Attributes:
        failure_threshold: Number of failures before opening circuit
        success_threshold: Number of successes to close circuit from half-open
        timeout_seconds: Seconds to wait before trying half-open
        window_seconds: Time window for counting failures
    """
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout_seconds: int = 60
    window_seconds: int = 300


@dataclass
class CircuitBreakerMetrics:
    """
    Metrics for circuit breaker.

    Attributes:
        total_requests: Total requests attempted
        successful_requests: Successful requests
        failed_requests: Failed requests
        rejected_requests: Requests rejected due to open circuit
        state_transitions: Number of state transitions
        last_failure_time: When last failure occurred
        last_success_time: When last success occurred
    """
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    rejected_requests: int = 0
    state_transitions: int = 0
    last_failure_time: Optional[datetime] = None
    last_success_time: Optional[datetime] = None


class CircuitBreaker:
    """
    Circuit breaker for agent operations.

    Implements the circuit breaker pattern to prevent cascading failures:
    - CLOSED: Normal operation
    - OPEN: Too many failures, block requests
    - HALF_OPEN: Testing recovery, allow limited requests

    Example:
        >>> breaker = CircuitBreaker(
        ...     name="researcher_agent",
        ...     config=CircuitBreakerConfig(
        ...         failure_threshold=5,
        ...         timeout_seconds=60
        ...     )
        ... )
        >>>
        >>> # Check if operation allowed
        >>> if breaker.can_execute():
        ...     try:
        ...         # Execute agent operation
        ...         result = execute_agent()
        ...         breaker.record_success()
        ...     except Exception as e:
        ...         breaker.record_failure()
        ...         raise
        >>> else:
        ...     print("Circuit breaker open, operation blocked")
    """

    def __init__(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ):
        """
        Initialize circuit breaker.

        Args:
            name: Circuit breaker name (usually agent name)
            config: Configuration (uses defaults if not provided)
        """
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.metrics = CircuitBreakerMetrics()

        # Failure tracking
        self._recent_failures: List[datetime] = []
        self._consecutive_successes = 0

        # State transition tracking
        self._last_state_change = datetime.now(timezone.utc)
        self._open_since: Optional[datetime] = None

        # Callbacks
        self._state_change_callbacks: List[Callable[[CircuitState, CircuitState], None]] = []

        self.logger = logging.getLogger(f"CircuitBreaker.{name}")

    def can_execute(self) -> bool:
        """
        Check if operation can be executed.

        Returns:
            True if operation allowed, False if circuit is open
        """
        self._update_state()

        if self.state == CircuitState.OPEN:
            self.metrics.rejected_requests += 1
            self.logger.warning(f"Circuit open for {self.name}, request rejected")
            return False

        return True

    def record_success(self):
        """Record successful operation."""
        self.metrics.total_requests += 1
        self.metrics.successful_requests += 1
        self.metrics.last_success_time = datetime.now(timezone.utc)

        if self.state == CircuitState.HALF_OPEN:
            self._consecutive_successes += 1

            # Check if enough successes to close circuit
            if self._consecutive_successes >= self.config.success_threshold:
                self._transition_to_closed()

    def record_failure(self):
        """Record failed operation."""
        self.metrics.total_requests += 1
        self.metrics.failed_requests += 1
        self.metrics.last_failure_time = datetime.now(timezone.utc)

        # Track recent failure
        self._recent_failures.append(datetime.now(timezone.utc))

        # Clean old failures outside window
        self._clean_old_failures()

        # Reset consecutive successes
        self._consecutive_successes = 0

        # Check if should open circuit
        if self.state == CircuitState.CLOSED:
            if len(self._recent_failures) >= self.config.failure_threshold:
                self._transition_to_open()
        elif self.state == CircuitState.HALF_OPEN:
            # Single failure in half-open = reopen
            self._transition_to_open()

    def reset(self):
        """Reset circuit breaker to closed state."""
        self._transition_to_closed()
        self._recent_failures.clear()
        self._consecutive_successes = 0
        self.logger.info(f"Circuit breaker {self.name} manually reset")

    def force_open(self):
        """Force circuit breaker to open state."""
        self._transition_to_open()
        self.logger.warning(f"Circuit breaker {self.name} manually opened")

    def get_state(self) -> CircuitState:
        """Get current state."""
        self._update_state()
        return self.state

    def get_metrics(self) -> CircuitBreakerMetrics:
        """Get circuit breaker metrics."""
        return self.metrics

    def on_state_change(self, callback: Callable[[CircuitState, CircuitState], None]):
        """
        Register callback for state changes.

        Args:
            callback: Function(old_state, new_state)
        """
        self._state_change_callbacks.append(callback)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "state": self.state.value,
            "config": {
                "failure_threshold": self.config.failure_threshold,
                "success_threshold": self.config.success_threshold,
                "timeout_seconds": self.config.timeout_seconds,
                "window_seconds": self.config.window_seconds
            },
            "metrics": {
                "total_requests": self.metrics.total_requests,
                "successful_requests": self.metrics.successful_requests,
                "failed_requests": self.metrics.failed_requests,
                "rejected_requests": self.metrics.rejected_requests,
                "state_transitions": self.metrics.state_transitions,
                "last_failure_time": self.metrics.last_failure_time.isoformat() if self.metrics.last_failure_time else None,
                "last_success_time": self.metrics.last_success_time.isoformat() if self.metrics.last_success_time else None
            },
            "recent_failures_count": len(self._recent_failures),
            "consecutive_successes": self._consecutive_successes,
            "open_since": self._open_since.isoformat() if self._open_since else None
        }

    def _update_state(self):
        """Update state based on timeout (open -> half-open transition)."""
        if self.state == CircuitState.OPEN:
            if self._open_since:
                elapsed = (datetime.now(timezone.utc) - self._open_since).total_seconds()

                if elapsed >= self.config.timeout_seconds:
                    self._transition_to_half_open()

    def _transition_to_closed(self):
        """Transition to CLOSED state."""
        old_state = self.state
        self.state = CircuitState.CLOSED
        self._last_state_change = datetime.now(timezone.utc)
        self._open_since = None
        self._recent_failures.clear()
        self._consecutive_successes = 0

        if old_state != CircuitState.CLOSED:
            self.metrics.state_transitions += 1
            self.logger.info(f"Circuit breaker {self.name}: {old_state.value} -> CLOSED")
            self._notify_state_change(old_state, CircuitState.CLOSED)

    def _transition_to_open(self):
        """Transition to OPEN state."""
        old_state = self.state
        self.state = CircuitState.OPEN
        self._last_state_change = datetime.now(timezone.utc)
        self._open_since = datetime.now(timezone.utc)
        self._consecutive_successes = 0

        if old_state != CircuitState.OPEN:
            self.metrics.state_transitions += 1
            self.logger.warning(f"Circuit breaker {self.name}: {old_state.value} -> OPEN (failures: {len(self._recent_failures)})")
            self._notify_state_change(old_state, CircuitState.OPEN)

    def _transition_to_half_open(self):
        """Transition to HALF_OPEN state."""
        old_state = self.state
        self.state = CircuitState.HALF_OPEN
        self._last_state_change = datetime.now(timezone.utc)
        self._consecutive_successes = 0

        if old_state != CircuitState.HALF_OPEN:
            self.metrics.state_transitions += 1
            self.logger.info(f"Circuit breaker {self.name}: {old_state.value} -> HALF_OPEN")
            self._notify_state_change(old_state, CircuitState.HALF_OPEN)

    def _clean_old_failures(self):
        """Remove failures outside the tracking window."""
        cutoff = datetime.now(timezone.utc) - timedelta(seconds=self.config.window_seconds)
        self._recent_failures = [
            failure_time for failure_time in self._recent_failures
            if failure_time >= cutoff
        ]

    def _notify_state_change(self, old_state: CircuitState, new_state: CircuitState):
        """Notify callbacks of state change."""
        for callback in self._state_change_callbacks:
            try:
                callback(old_state, new_state)
            except Exception as e:
                self.logger.error(f"State change callback failed: {e}")


class CircuitBreakerRegistry:
    """
    Registry for managing multiple circuit breakers.

    Example:
        >>> registry = CircuitBreakerRegistry()
        >>>
        >>> # Get or create circuit breaker for agent
        >>> breaker = registry.get_breaker("researcher_agent")
        >>>
        >>> # Check status of all breakers
        >>> status = registry.get_status()
        >>> for name, state in status.items():
        ...     print(f"{name}: {state}")
    """

    def __init__(self, default_config: Optional[CircuitBreakerConfig] = None):
        """
        Initialize circuit breaker registry.

        Args:
            default_config: Default config for new breakers
        """
        self.default_config = default_config or CircuitBreakerConfig()
        self._breakers: Dict[str, CircuitBreaker] = {}
        self.logger = logging.getLogger("CircuitBreakerRegistry")

    def get_breaker(
        self,
        name: str,
        config: Optional[CircuitBreakerConfig] = None
    ) -> CircuitBreaker:
        """
        Get or create circuit breaker.

        Args:
            name: Breaker name
            config: Config (uses default if not provided)

        Returns:
            CircuitBreaker instance
        """
        if name not in self._breakers:
            breaker_config = config or self.default_config
            self._breakers[name] = CircuitBreaker(name, breaker_config)
            self.logger.info(f"Created circuit breaker: {name}")

        return self._breakers[name]

    def remove_breaker(self, name: str) -> bool:
        """
        Remove circuit breaker.

        Args:
            name: Breaker name

        Returns:
            True if removed, False if not found
        """
        if name in self._breakers:
            del self._breakers[name]
            self.logger.info(f"Removed circuit breaker: {name}")
            return True
        return False

    def get_status(self) -> Dict[str, str]:
        """
        Get status of all circuit breakers.

        Returns:
            Dict mapping breaker name to state
        """
        return {
            name: breaker.get_state().value
            for name, breaker in self._breakers.items()
        }

    def get_all_metrics(self) -> Dict[str, Dict[str, Any]]:
        """
        Get metrics for all circuit breakers.

        Returns:
            Dict mapping breaker name to metrics dict
        """
        return {
            name: breaker.to_dict()
            for name, breaker in self._breakers.items()
        }

    def reset_all(self):
        """Reset all circuit breakers."""
        for breaker in self._breakers.values():
            breaker.reset()
        self.logger.info("Reset all circuit breakers")

    def get_open_breakers(self) -> List[str]:
        """
        Get names of all open circuit breakers.

        Returns:
            List of breaker names in OPEN state
        """
        return [
            name for name, breaker in self._breakers.items()
            if breaker.get_state() == CircuitState.OPEN
        ]
