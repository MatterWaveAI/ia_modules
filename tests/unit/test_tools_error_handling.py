"""
Unit tests for error handling strategies.

Tests RetryExecutor, CircuitBreaker, FallbackExecutor,
CompositeErrorHandler, and decorators.
"""

from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ia_modules.tools.error_handling import (
    RetryExecutor,
    RetryConfig,
    RetryStrategy,
    CircuitBreaker,
    CircuitBreakerConfig,
    CircuitBreakerError,
    CircuitState,
    FallbackExecutor,
    FallbackConfig,
    CompositeErrorHandler,
    with_retry,
    with_circuit_breaker,
    with_fallback,
)


# --------------------------------------------------------------------------- #
# RetryExecutor
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
class TestRetryExecutor:
    """Test RetryExecutor retry logic and backoff strategies."""

    async def test_success_on_first_attempt(self):
        """Function succeeding on first call is not retried."""
        func = AsyncMock(return_value="ok")
        executor = RetryExecutor(RetryConfig(max_attempts=3))

        result = await executor.execute(func)

        assert result == "ok"
        assert func.await_count == 1

    async def test_success_after_transient_failures(self):
        """Function succeeds after initial failures within max_attempts."""
        func = AsyncMock(side_effect=[ValueError("fail1"), ValueError("fail2"), "ok"])
        config = RetryConfig(
            max_attempts=3,
            strategy=RetryStrategy.IMMEDIATE,
            retryable_exceptions=(ValueError,),
        )
        executor = RetryExecutor(config)

        result = await executor.execute(func)

        assert result == "ok"
        assert func.await_count == 3

    async def test_permanent_failure_raises_after_max_attempts(self):
        """Exception raised after all attempts exhausted."""
        func = AsyncMock(side_effect=ValueError("permanent"))
        config = RetryConfig(
            max_attempts=4,
            strategy=RetryStrategy.IMMEDIATE,
            retryable_exceptions=(ValueError,),
        )
        executor = RetryExecutor(config)

        with pytest.raises(ValueError, match="permanent"):
            await executor.execute(func)

        assert func.await_count == 4

    async def test_non_retryable_exception_raises_immediately(self):
        """Exceptions not in retryable_exceptions are not retried."""
        func = AsyncMock(side_effect=TypeError("wrong type"))
        config = RetryConfig(
            max_attempts=5,
            strategy=RetryStrategy.IMMEDIATE,
            retryable_exceptions=(ValueError,),
        )
        executor = RetryExecutor(config)

        with pytest.raises(TypeError, match="wrong type"):
            await executor.execute(func)

        assert func.await_count == 1

    async def test_on_retry_callback_invoked(self):
        """on_retry callback is called before each retry."""
        callback = MagicMock()
        func = AsyncMock(side_effect=[ValueError("e1"), ValueError("e2"), "ok"])
        config = RetryConfig(
            max_attempts=3,
            strategy=RetryStrategy.IMMEDIATE,
            retryable_exceptions=(ValueError,),
            on_retry=callback,
        )
        executor = RetryExecutor(config)

        await executor.execute(func)

        assert callback.call_count == 2
        # First call: attempt=1, exception
        assert callback.call_args_list[0][0][0] == 1
        assert isinstance(callback.call_args_list[0][0][1], ValueError)
        # Second call: attempt=2
        assert callback.call_args_list[1][0][0] == 2

    async def test_arguments_forwarded_to_function(self):
        """Positional and keyword arguments are forwarded correctly."""
        async def func(a, b, c=10):
            return a + b + c

        executor = RetryExecutor(RetryConfig(max_attempts=1))
        result = await executor.execute(func, 1, 2, c=3)

        assert result == 6

    async def test_default_config(self):
        """RetryExecutor works with default configuration."""
        func = AsyncMock(return_value=42)
        executor = RetryExecutor()

        result = await executor.execute(func)

        assert result == 42

    # ---- Backoff strategy calculations ---- #

    async def test_exponential_backoff_delay(self):
        """Exponential backoff computes correct delays."""
        config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            initial_delay=1.0,
            backoff_multiplier=2.0,
            max_delay=60.0,
        )
        executor = RetryExecutor(config)

        assert executor._calculate_delay(1) == 1.0   # 1 * 2^0
        assert executor._calculate_delay(2) == 2.0   # 1 * 2^1
        assert executor._calculate_delay(3) == 4.0   # 1 * 2^2
        assert executor._calculate_delay(4) == 8.0   # 1 * 2^3

    async def test_exponential_backoff_capped_at_max(self):
        """Exponential backoff respects max_delay."""
        config = RetryConfig(
            strategy=RetryStrategy.EXPONENTIAL_BACKOFF,
            initial_delay=1.0,
            backoff_multiplier=10.0,
            max_delay=5.0,
        )
        executor = RetryExecutor(config)

        assert executor._calculate_delay(3) == 5.0  # 1*10^2=100, capped at 5

    async def test_linear_backoff_delay(self):
        """Linear backoff computes correct delays."""
        config = RetryConfig(
            strategy=RetryStrategy.LINEAR_BACKOFF,
            initial_delay=2.0,
            max_delay=20.0,
        )
        executor = RetryExecutor(config)

        assert executor._calculate_delay(1) == 2.0   # 2 * 1
        assert executor._calculate_delay(3) == 6.0   # 2 * 3
        assert executor._calculate_delay(5) == 10.0  # 2 * 5

    async def test_linear_backoff_capped_at_max(self):
        """Linear backoff respects max_delay."""
        config = RetryConfig(
            strategy=RetryStrategy.LINEAR_BACKOFF,
            initial_delay=5.0,
            max_delay=10.0,
        )
        executor = RetryExecutor(config)

        assert executor._calculate_delay(5) == 10.0  # 5*5=25, capped at 10

    async def test_fixed_delay(self):
        """Fixed delay returns initial_delay regardless of attempt."""
        config = RetryConfig(
            strategy=RetryStrategy.FIXED_DELAY,
            initial_delay=3.0,
            max_delay=60.0,
        )
        executor = RetryExecutor(config)

        assert executor._calculate_delay(1) == 3.0
        assert executor._calculate_delay(10) == 3.0

    async def test_fixed_delay_capped_at_max(self):
        """Fixed delay respects max_delay when initial > max."""
        config = RetryConfig(
            strategy=RetryStrategy.FIXED_DELAY,
            initial_delay=100.0,
            max_delay=5.0,
        )
        executor = RetryExecutor(config)

        assert executor._calculate_delay(1) == 5.0

    async def test_immediate_strategy_no_delay(self):
        """Immediate strategy returns zero delay."""
        config = RetryConfig(strategy=RetryStrategy.IMMEDIATE)
        executor = RetryExecutor(config)

        assert executor._calculate_delay(1) == 0
        assert executor._calculate_delay(99) == 0

    async def test_sleep_called_between_retries(self):
        """asyncio.sleep is called with the calculated delay between retries."""
        func = AsyncMock(side_effect=[ValueError("fail"), "ok"])
        config = RetryConfig(
            max_attempts=2,
            strategy=RetryStrategy.FIXED_DELAY,
            initial_delay=1.5,
            retryable_exceptions=(ValueError,),
        )
        executor = RetryExecutor(config)

        with patch("ia_modules.tools.error_handling.asyncio.sleep", new_callable=AsyncMock) as mock_sleep:
            result = await executor.execute(func)

        assert result == "ok"
        mock_sleep.assert_awaited_once_with(1.5)


# --------------------------------------------------------------------------- #
# CircuitBreaker
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
class TestCircuitBreaker:
    """Test CircuitBreaker state transitions."""

    async def test_starts_closed(self):
        """Circuit breaker starts in CLOSED state."""
        breaker = CircuitBreaker()
        assert breaker.state == CircuitState.CLOSED

    async def test_closed_state_allows_calls(self):
        """Calls succeed when circuit is closed."""
        breaker = CircuitBreaker()
        func = AsyncMock(return_value="success")

        result = await breaker.call(func)

        assert result == "success"

    async def test_opens_after_failure_threshold(self):
        """Circuit opens after reaching failure_threshold."""
        config = CircuitBreakerConfig(failure_threshold=3)
        breaker = CircuitBreaker(config)
        func = AsyncMock(side_effect=RuntimeError("fail"))

        for _ in range(3):
            with pytest.raises(RuntimeError):
                await breaker.call(func)

        assert breaker.state == CircuitState.OPEN

    async def test_open_state_rejects_calls(self):
        """Open circuit rejects calls with CircuitBreakerError."""
        config = CircuitBreakerConfig(failure_threshold=2, timeout=3600)
        breaker = CircuitBreaker(config)
        func = AsyncMock(side_effect=RuntimeError("fail"))

        # Trigger open state
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(func)

        assert breaker.state == CircuitState.OPEN

        # Next call should be rejected
        with pytest.raises(CircuitBreakerError, match="Circuit breaker is open"):
            await breaker.call(func)

    async def test_transitions_to_half_open_after_timeout(self):
        """Circuit transitions to HALF_OPEN after timeout elapses."""
        config = CircuitBreakerConfig(failure_threshold=2, timeout=1.0)
        breaker = CircuitBreaker(config)
        func = AsyncMock(side_effect=[RuntimeError("f1"), RuntimeError("f2"), "ok"])

        # Open the circuit
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(func)

        assert breaker.state == CircuitState.OPEN

        # Simulate timeout elapsed
        breaker.last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=2)

        result = await breaker.call(func)

        assert breaker.state == CircuitState.HALF_OPEN or breaker.state == CircuitState.CLOSED
        assert result == "ok"

    async def test_half_open_success_closes_circuit(self):
        """Enough successes in HALF_OPEN close the circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=2,
            success_threshold=2,
            timeout=0.0,
            half_open_max_calls=5,
        )
        breaker = CircuitBreaker(config)
        fail_func = AsyncMock(side_effect=RuntimeError("fail"))

        # Open the circuit
        for _ in range(2):
            with pytest.raises(RuntimeError):
                await breaker.call(fail_func)

        assert breaker.state == CircuitState.OPEN

        # Allow transition to half-open
        breaker.last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=1)

        ok_func = AsyncMock(return_value="ok")

        # Need success_threshold=2 successes to close
        await breaker.call(ok_func)
        assert breaker.state == CircuitState.HALF_OPEN

        await breaker.call(ok_func)
        assert breaker.state == CircuitState.CLOSED

    async def test_half_open_failure_reopens_circuit(self):
        """A failure in HALF_OPEN re-opens the circuit."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            timeout=0.0,
            half_open_max_calls=5,
        )
        breaker = CircuitBreaker(config)
        fail_func = AsyncMock(side_effect=RuntimeError("fail"))

        # Open the circuit
        with pytest.raises(RuntimeError):
            await breaker.call(fail_func)

        assert breaker.state == CircuitState.OPEN

        # Transition to half-open
        breaker.last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=1)

        # Failure in half-open reopens
        with pytest.raises(RuntimeError):
            await breaker.call(fail_func)

        assert breaker.state == CircuitState.OPEN

    async def test_half_open_max_calls_enforced(self):
        """Half-open state limits concurrent calls."""
        config = CircuitBreakerConfig(
            failure_threshold=1,
            timeout=0.0,
            half_open_max_calls=1,
        )
        breaker = CircuitBreaker(config)

        # Open the circuit
        fail_func = AsyncMock(side_effect=RuntimeError("fail"))
        with pytest.raises(RuntimeError):
            await breaker.call(fail_func)

        breaker.last_failure_time = datetime.now(timezone.utc) - timedelta(seconds=1)

        # First call transitions to half-open and uses the one allowed call
        ok_func = AsyncMock(return_value="ok")
        await breaker.call(ok_func)

        # If not yet closed, second call should be rejected
        if breaker.state == CircuitState.HALF_OPEN:
            with pytest.raises(CircuitBreakerError, match="half-open limit reached"):
                await breaker.call(ok_func)

    async def test_reset_returns_to_closed(self):
        """Manual reset restores circuit to clean CLOSED state."""
        config = CircuitBreakerConfig(failure_threshold=1)
        breaker = CircuitBreaker(config)
        fail_func = AsyncMock(side_effect=RuntimeError("fail"))

        with pytest.raises(RuntimeError):
            await breaker.call(fail_func)

        assert breaker.state == CircuitState.OPEN

        breaker.reset()

        assert breaker.state == CircuitState.CLOSED
        assert breaker.failure_count == 0
        assert breaker.success_count == 0
        assert breaker.last_failure_time is None

    async def test_success_resets_failure_count(self):
        """A success in CLOSED state resets failure_count to zero."""
        config = CircuitBreakerConfig(failure_threshold=5)
        breaker = CircuitBreaker(config)

        fail_func = AsyncMock(side_effect=RuntimeError("fail"))
        ok_func = AsyncMock(return_value="ok")

        # Accumulate some failures (below threshold)
        for _ in range(3):
            with pytest.raises(RuntimeError):
                await breaker.call(fail_func)

        assert breaker.failure_count == 3

        # One success resets count
        await breaker.call(ok_func)
        assert breaker.failure_count == 0

    async def test_arguments_forwarded(self):
        """Arguments are passed through to the wrapped function."""
        breaker = CircuitBreaker()

        async def add(a, b):
            return a + b

        result = await breaker.call(add, 3, 7)
        assert result == 10

    async def test_kwargs_forwarded(self):
        """Keyword arguments are passed through to the wrapped function."""
        breaker = CircuitBreaker()

        async def greet(name, greeting="Hello"):
            return f"{greeting}, {name}"

        result = await breaker.call(greet, "World", greeting="Hi")
        assert result == "Hi, World"

    async def test_should_attempt_reset_no_failure_time(self):
        """_should_attempt_reset returns True when last_failure_time is None."""
        breaker = CircuitBreaker()
        assert breaker._should_attempt_reset() is True


# --------------------------------------------------------------------------- #
# FallbackExecutor
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
class TestFallbackExecutor:
    """Test FallbackExecutor fallback chain."""

    async def test_primary_succeeds_no_fallback(self):
        """Primary function succeeding skips fallbacks."""
        primary = AsyncMock(return_value="primary_result")
        fallback = AsyncMock(return_value="fallback_result")
        config = FallbackConfig(fallback_functions=[fallback])
        executor = FallbackExecutor(config)

        result = await executor.execute(primary)

        assert result == "primary_result"
        fallback.assert_not_awaited()

    async def test_fallback_used_on_primary_failure(self):
        """Fallback is called when primary fails."""
        primary = AsyncMock(side_effect=ValueError("primary failed"))
        fallback = AsyncMock(return_value="fallback_result")
        config = FallbackConfig(
            fallback_functions=[fallback],
            fallback_on_exceptions=(ValueError,),
        )
        executor = FallbackExecutor(config)

        result = await executor.execute(primary)

        assert result == "fallback_result"

    async def test_fallback_chain_order(self):
        """Fallbacks are tried in order until one succeeds."""
        primary = AsyncMock(side_effect=ValueError("fail"))
        fb1 = AsyncMock(side_effect=ValueError("fb1 fail"))
        fb2 = AsyncMock(return_value="fb2_result")
        fb3 = AsyncMock(return_value="fb3_result")
        config = FallbackConfig(
            fallback_functions=[fb1, fb2, fb3],
            fallback_on_exceptions=(ValueError,),
        )
        executor = FallbackExecutor(config)

        result = await executor.execute(primary)

        assert result == "fb2_result"
        fb3.assert_not_awaited()

    async def test_all_fail_raises_last_exception(self):
        """When all functions fail, the last exception is raised."""
        primary = AsyncMock(side_effect=ValueError("p"))
        fb1 = AsyncMock(side_effect=ValueError("final error"))
        config = FallbackConfig(
            fallback_functions=[fb1],
            fallback_on_exceptions=(ValueError,),
        )
        executor = FallbackExecutor(config)

        with pytest.raises(ValueError, match="final error"):
            await executor.execute(primary)

    async def test_default_value_returned_on_all_failures(self):
        """Default value returned when configured and all functions fail."""
        primary = AsyncMock(side_effect=ValueError("fail"))
        config = FallbackConfig(
            fallback_functions=[],
            fallback_on_exceptions=(ValueError,),
            return_default_on_all_failures=True,
            default_value="default",
        )
        executor = FallbackExecutor(config)

        result = await executor.execute(primary)

        assert result == "default"

    async def test_non_matching_exception_not_caught(self):
        """Exceptions not in fallback_on_exceptions propagate immediately."""
        primary = AsyncMock(side_effect=TypeError("type error"))
        fallback = AsyncMock(return_value="fallback")
        config = FallbackConfig(
            fallback_functions=[fallback],
            fallback_on_exceptions=(ValueError,),
        )
        executor = FallbackExecutor(config)

        with pytest.raises(TypeError, match="type error"):
            await executor.execute(primary)

        fallback.assert_not_awaited()

    async def test_arguments_forwarded(self):
        """Arguments passed to all functions in the chain."""
        async def primary(x, y):
            raise ValueError("fail")

        async def fallback(x, y):
            return x + y

        config = FallbackConfig(
            fallback_functions=[fallback],
            fallback_on_exceptions=(ValueError,),
        )
        executor = FallbackExecutor(config)

        result = await executor.execute(primary, 3, 5)
        assert result == 8

    async def test_default_config(self):
        """FallbackExecutor works with default config (no fallbacks)."""
        func = AsyncMock(return_value="ok")
        executor = FallbackExecutor()

        result = await executor.execute(func)
        assert result == "ok"


# --------------------------------------------------------------------------- #
# CompositeErrorHandler
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
class TestCompositeErrorHandler:
    """Test CompositeErrorHandler combining strategies."""

    async def test_retry_only(self):
        """Handler with only retry config retries on failure."""
        func = AsyncMock(side_effect=[ValueError("e"), "ok"])
        handler = CompositeErrorHandler(
            retry_config=RetryConfig(
                max_attempts=2,
                strategy=RetryStrategy.IMMEDIATE,
                retryable_exceptions=(ValueError,),
            )
        )

        result = await handler.execute(func)

        assert result == "ok"
        assert func.await_count == 2

    async def test_circuit_breaker_only(self):
        """Handler with only circuit breaker protects calls."""
        handler = CompositeErrorHandler(
            circuit_breaker_config=CircuitBreakerConfig(failure_threshold=2)
        )
        func = AsyncMock(side_effect=RuntimeError("fail"))

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await handler.execute(func)

        with pytest.raises(CircuitBreakerError):
            await handler.execute(func)

    async def test_fallback_only(self):
        """Handler with only fallback config tries fallback chain."""
        primary = AsyncMock(side_effect=ValueError("fail"))
        fallback = AsyncMock(return_value="fallback_ok")
        handler = CompositeErrorHandler(
            fallback_config=FallbackConfig(
                fallback_functions=[fallback],
                fallback_on_exceptions=(ValueError,),
            )
        )

        result = await handler.execute(primary)
        assert result == "fallback_ok"

    async def test_no_config_passthrough(self):
        """Handler with no config passes through to function."""
        func = AsyncMock(return_value="direct")
        handler = CompositeErrorHandler()

        result = await handler.execute(func)
        assert result == "direct"

    async def test_circuit_breaker_with_fallback(self):
        """When circuit breaker + fallback configured, fallback is used on failure."""
        config_cb = CircuitBreakerConfig(failure_threshold=1, timeout=3600)
        fallback = AsyncMock(return_value="fallback_result")
        config_fb = FallbackConfig(
            fallback_functions=[fallback],
            fallback_on_exceptions=(Exception,),
        )
        handler = CompositeErrorHandler(
            circuit_breaker_config=config_cb,
            fallback_config=config_fb,
        )
        func = AsyncMock(side_effect=RuntimeError("fail"))

        # First call: primary fails, composite catches and uses fallback
        result = await handler.execute(func)
        assert result == "fallback_result"

        # Second call: circuit now open, still falls back
        result2 = await handler.execute(func)
        assert result2 == "fallback_result"

    async def test_retry_with_circuit_breaker(self):
        """Retry inside circuit breaker works correctly."""
        func = AsyncMock(side_effect=[ValueError("e"), "ok"])
        handler = CompositeErrorHandler(
            retry_config=RetryConfig(
                max_attempts=2,
                strategy=RetryStrategy.IMMEDIATE,
                retryable_exceptions=(ValueError,),
            ),
            circuit_breaker_config=CircuitBreakerConfig(failure_threshold=5),
        )

        result = await handler.execute(func)
        assert result == "ok"


# --------------------------------------------------------------------------- #
# Decorators
# --------------------------------------------------------------------------- #


@pytest.mark.asyncio
class TestDecorators:
    """Test with_retry, with_circuit_breaker, with_fallback decorators."""

    async def test_with_retry_decorator(self):
        """@with_retry retries decorated function."""
        call_count = 0

        @with_retry(RetryConfig(
            max_attempts=3,
            strategy=RetryStrategy.IMMEDIATE,
            retryable_exceptions=(ValueError,),
        ))
        async def flaky():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ValueError("not yet")
            return "done"

        result = await flaky()
        assert result == "done"
        assert call_count == 3

    async def test_with_circuit_breaker_decorator(self):
        """@with_circuit_breaker wraps function with circuit breaker."""
        @with_circuit_breaker(CircuitBreakerConfig(failure_threshold=2, timeout=3600))
        async def failing():
            raise RuntimeError("always fails")

        for _ in range(2):
            with pytest.raises(RuntimeError):
                await failing()

        with pytest.raises(CircuitBreakerError):
            await failing()

    async def test_with_fallback_decorator(self):
        """@with_fallback provides fallback for decorated function."""
        async def backup():
            return "backup_value"

        @with_fallback(backup)
        async def primary():
            raise ValueError("broken")

        result = await primary()
        assert result == "backup_value"

    async def test_with_fallback_default_value(self):
        """@with_fallback returns default when all fail."""
        async def also_fails():
            raise ValueError("also broken")

        @with_fallback(also_fails, default_value="safe_default")
        async def primary():
            raise ValueError("broken")

        result = await primary()
        assert result == "safe_default"

    async def test_with_retry_preserves_function_name(self):
        """@with_retry preserves original function name."""
        @with_retry()
        async def my_function():
            return True

        assert my_function.__name__ == "my_function"

    async def test_with_circuit_breaker_preserves_function_name(self):
        """@with_circuit_breaker preserves original function name."""
        @with_circuit_breaker()
        async def my_function():
            return True

        assert my_function.__name__ == "my_function"

    async def test_with_fallback_preserves_function_name(self):
        """@with_fallback preserves original function name."""
        async def fb():
            return None

        @with_fallback(fb)
        async def my_function():
            return True

        assert my_function.__name__ == "my_function"


# --------------------------------------------------------------------------- #
# RetryStrategy enum / config dataclasses
# --------------------------------------------------------------------------- #


class TestRetryStrategy:
    """Test RetryStrategy enum values."""

    def test_all_strategies_defined(self):
        """All expected retry strategies exist."""
        assert RetryStrategy.EXPONENTIAL_BACKOFF.value == "exponential_backoff"
        assert RetryStrategy.LINEAR_BACKOFF.value == "linear_backoff"
        assert RetryStrategy.FIXED_DELAY.value == "fixed_delay"
        assert RetryStrategy.IMMEDIATE.value == "immediate"


class TestCircuitState:
    """Test CircuitState enum values."""

    def test_all_states_defined(self):
        """All expected circuit states exist."""
        assert CircuitState.CLOSED.value == "closed"
        assert CircuitState.OPEN.value == "open"
        assert CircuitState.HALF_OPEN.value == "half_open"


class TestRetryConfig:
    """Test RetryConfig defaults."""

    def test_defaults(self):
        """RetryConfig has correct default values."""
        config = RetryConfig()
        assert config.max_attempts == 3
        assert config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.backoff_multiplier == 2.0
        assert config.retryable_exceptions == (Exception,)
        assert config.on_retry is None


class TestCircuitBreakerConfig:
    """Test CircuitBreakerConfig defaults."""

    def test_defaults(self):
        """CircuitBreakerConfig has correct default values."""
        config = CircuitBreakerConfig()
        assert config.failure_threshold == 5
        assert config.success_threshold == 2
        assert config.timeout == 60.0
        assert config.half_open_max_calls == 1


class TestFallbackConfig:
    """Test FallbackConfig defaults."""

    def test_defaults(self):
        """FallbackConfig has correct default values."""
        config = FallbackConfig()
        assert config.fallback_functions == []
        assert config.fallback_on_exceptions == (Exception,)
        assert config.return_default_on_all_failures is False
        assert config.default_value is None
