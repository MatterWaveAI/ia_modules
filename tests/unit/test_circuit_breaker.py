"""Tests for circuit breaker."""

import time

from ia_modules.reliability.circuit_breaker import (
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitState,
    CircuitBreakerRegistry
)


def test_circuit_breaker_creation():
    """Test creating circuit breaker."""
    breaker = CircuitBreaker("test_agent")

    assert breaker.name == "test_agent"
    assert breaker.state == CircuitState.CLOSED
    assert breaker.metrics.total_requests == 0


def test_circuit_breaker_with_config():
    """Test creating circuit breaker with custom config."""
    config = CircuitBreakerConfig(
        failure_threshold=3,
        success_threshold=2,
        timeout_seconds=30
    )

    breaker = CircuitBreaker("test_agent", config)

    assert breaker.config.failure_threshold == 3
    assert breaker.config.success_threshold == 2
    assert breaker.config.timeout_seconds == 30


def test_can_execute_when_closed():
    """Test that operations are allowed when circuit is closed."""
    breaker = CircuitBreaker("test_agent")

    assert breaker.can_execute() is True
    assert breaker.state == CircuitState.CLOSED


def test_record_success():
    """Test recording successful operation."""
    breaker = CircuitBreaker("test_agent")

    breaker.record_success()

    assert breaker.metrics.total_requests == 1
    assert breaker.metrics.successful_requests == 1
    assert breaker.metrics.failed_requests == 0
    assert breaker.metrics.last_success_time is not None


def test_record_failure():
    """Test recording failed operation."""
    breaker = CircuitBreaker("test_agent")

    breaker.record_failure()

    assert breaker.metrics.total_requests == 1
    assert breaker.metrics.successful_requests == 0
    assert breaker.metrics.failed_requests == 1
    assert breaker.metrics.last_failure_time is not None


def test_circuit_opens_on_threshold():
    """Test that circuit opens after failure threshold."""
    config = CircuitBreakerConfig(failure_threshold=3)
    breaker = CircuitBreaker("test_agent", config)

    # Record failures
    for i in range(3):
        breaker.record_failure()

    # Circuit should be open
    assert breaker.state == CircuitState.OPEN
    assert breaker.metrics.state_transitions == 1


def test_requests_rejected_when_open():
    """Test that requests are rejected when circuit is open."""
    config = CircuitBreakerConfig(failure_threshold=3)
    breaker = CircuitBreaker("test_agent", config)

    # Open the circuit
    for i in range(3):
        breaker.record_failure()

    # Requests should be rejected
    assert breaker.can_execute() is False
    assert breaker.metrics.rejected_requests == 1


def test_circuit_transitions_to_half_open():
    """Test circuit transitions to half-open after timeout."""
    config = CircuitBreakerConfig(
        failure_threshold=2,
        timeout_seconds=1  # Short timeout for testing
    )
    breaker = CircuitBreaker("test_agent", config)

    # Open the circuit
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN

    # Wait for timeout
    time.sleep(1.1)

    # Check state - should transition to half-open
    breaker._update_state()
    assert breaker.state == CircuitState.HALF_OPEN


def test_half_open_closes_on_success():
    """Test that half-open circuit closes after successful requests."""
    config = CircuitBreakerConfig(
        failure_threshold=2,
        success_threshold=2,
        timeout_seconds=1
    )
    breaker = CircuitBreaker("test_agent", config)

    # Open the circuit
    breaker.record_failure()
    breaker.record_failure()

    # Wait and transition to half-open
    time.sleep(1.1)
    breaker._update_state()
    assert breaker.state == CircuitState.HALF_OPEN

    # Record successes
    breaker.record_success()
    breaker.record_success()

    # Should be closed now
    assert breaker.state == CircuitState.CLOSED


def test_half_open_reopens_on_failure():
    """Test that half-open circuit reopens on single failure."""
    config = CircuitBreakerConfig(
        failure_threshold=2,
        timeout_seconds=1
    )
    breaker = CircuitBreaker("test_agent", config)

    # Open the circuit
    breaker.record_failure()
    breaker.record_failure()

    # Wait and transition to half-open
    time.sleep(1.1)
    breaker._update_state()
    assert breaker.state == CircuitState.HALF_OPEN

    # Single failure should reopen
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN


def test_reset_circuit():
    """Test manually resetting circuit breaker."""
    config = CircuitBreakerConfig(failure_threshold=2)
    breaker = CircuitBreaker("test_agent", config)

    # Open the circuit
    breaker.record_failure()
    breaker.record_failure()
    assert breaker.state == CircuitState.OPEN

    # Reset
    breaker.reset()

    assert breaker.state == CircuitState.CLOSED
    assert len(breaker._recent_failures) == 0
    assert breaker._consecutive_successes == 0


def test_force_open():
    """Test manually forcing circuit open."""
    breaker = CircuitBreaker("test_agent")

    assert breaker.state == CircuitState.CLOSED

    breaker.force_open()

    assert breaker.state == CircuitState.OPEN


def test_failure_window():
    """Test that old failures are not counted."""
    config = CircuitBreakerConfig(
        failure_threshold=3,
        window_seconds=2  # Short window
    )
    breaker = CircuitBreaker("test_agent", config)

    # Record 2 failures
    breaker.record_failure()
    breaker.record_failure()

    # Wait for window to expire
    time.sleep(2.1)

    # Record another failure
    breaker.record_failure()

    # Should still be closed (only 1 failure in window)
    assert breaker.state == CircuitState.CLOSED


def test_state_change_callback():
    """Test state change callback."""
    state_changes = []

    def callback(old_state, new_state):
        state_changes.append((old_state, new_state))

    config = CircuitBreakerConfig(failure_threshold=2)
    breaker = CircuitBreaker("test_agent", config)
    breaker.on_state_change(callback)

    # Open circuit
    breaker.record_failure()
    breaker.record_failure()

    # Should have recorded state change
    assert len(state_changes) == 1
    assert state_changes[0] == (CircuitState.CLOSED, CircuitState.OPEN)


def test_get_metrics():
    """Test getting circuit breaker metrics."""
    breaker = CircuitBreaker("test_agent")

    breaker.record_success()
    breaker.record_failure()

    metrics = breaker.get_metrics()

    assert metrics.total_requests == 2
    assert metrics.successful_requests == 1
    assert metrics.failed_requests == 1


def test_to_dict():
    """Test converting circuit breaker to dictionary."""
    config = CircuitBreakerConfig(failure_threshold=5)
    breaker = CircuitBreaker("test_agent", config)

    breaker.record_success()

    data = breaker.to_dict()

    assert data["name"] == "test_agent"
    assert data["state"] == "closed"
    assert data["config"]["failure_threshold"] == 5
    assert data["metrics"]["successful_requests"] == 1


def test_registry_creation():
    """Test creating circuit breaker registry."""
    registry = CircuitBreakerRegistry()

    assert len(registry._breakers) == 0


def test_registry_get_breaker():
    """Test getting breaker from registry."""
    registry = CircuitBreakerRegistry()

    breaker1 = registry.get_breaker("agent1")
    breaker2 = registry.get_breaker("agent1")  # Same instance

    assert breaker1 is breaker2
    assert len(registry._breakers) == 1


def test_registry_get_breaker_with_config():
    """Test getting breaker with custom config."""
    config = CircuitBreakerConfig(failure_threshold=10)
    registry = CircuitBreakerRegistry()

    breaker = registry.get_breaker("agent1", config)

    assert breaker.config.failure_threshold == 10


def test_registry_remove_breaker():
    """Test removing breaker from registry."""
    registry = CircuitBreakerRegistry()

    registry.get_breaker("agent1")
    result = registry.remove_breaker("agent1")

    assert result is True
    assert len(registry._breakers) == 0

    # Try removing non-existent
    result = registry.remove_breaker("nonexistent")
    assert result is False


def test_registry_get_status():
    """Test getting status of all breakers."""
    config = CircuitBreakerConfig(failure_threshold=2)
    registry = CircuitBreakerRegistry()

    breaker1 = registry.get_breaker("agent1", config)
    registry.get_breaker("agent2", config)

    # Open one circuit
    breaker1.record_failure()
    breaker1.record_failure()

    status = registry.get_status()

    assert status["agent1"] == "open"
    assert status["agent2"] == "closed"


def test_registry_get_all_metrics():
    """Test getting metrics for all breakers."""
    registry = CircuitBreakerRegistry()

    breaker1 = registry.get_breaker("agent1")
    breaker2 = registry.get_breaker("agent2")

    breaker1.record_success()
    breaker2.record_failure()

    metrics = registry.get_all_metrics()

    assert "agent1" in metrics
    assert "agent2" in metrics
    assert metrics["agent1"]["metrics"]["successful_requests"] == 1
    assert metrics["agent2"]["metrics"]["failed_requests"] == 1


def test_registry_reset_all():
    """Test resetting all breakers."""
    config = CircuitBreakerConfig(failure_threshold=2)
    registry = CircuitBreakerRegistry()

    breaker1 = registry.get_breaker("agent1", config)
    breaker2 = registry.get_breaker("agent2", config)

    # Open both circuits
    for _ in range(2):
        breaker1.record_failure()
        breaker2.record_failure()

    assert breaker1.state == CircuitState.OPEN
    assert breaker2.state == CircuitState.OPEN

    # Reset all
    registry.reset_all()

    assert breaker1.state == CircuitState.CLOSED
    assert breaker2.state == CircuitState.CLOSED


def test_registry_get_open_breakers():
    """Test getting list of open breakers."""
    config = CircuitBreakerConfig(failure_threshold=2)
    registry = CircuitBreakerRegistry()

    breaker1 = registry.get_breaker("agent1", config)
    breaker2 = registry.get_breaker("agent2", config)
    registry.get_breaker("agent3", config)

    # Open two circuits
    for _ in range(2):
        breaker1.record_failure()
        breaker2.record_failure()

    open_breakers = registry.get_open_breakers()

    assert len(open_breakers) == 2
    assert "agent1" in open_breakers
    assert "agent2" in open_breakers
    assert "agent3" not in open_breakers
