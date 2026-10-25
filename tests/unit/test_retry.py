"""
Unit tests for retry strategy system
"""

import pytest
import asyncio
from unittest.mock import AsyncMock

from ia_modules.pipeline.retry import (
    RetryConfig,
    RetryStrategy,
    retry,
    retry_with_timeout,
    CircuitBreaker,
    CircuitBreakerOpenError
)
from ia_modules.pipeline.errors import (
    NetworkError,
    ValidationError
)


class TestRetryConfig:
    """Test retry configuration"""

    def test_default_config(self):
        """Test default configuration values"""
        config = RetryConfig()

        assert config.max_attempts == 3
        assert config.initial_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
        assert NetworkError in config.retryable_exceptions

    def test_custom_config(self):
        """Test custom configuration"""
        config = RetryConfig(
            max_attempts=5,
            initial_delay=2.0,
            max_delay=120.0,
            exponential_base=3.0,
            jitter=False
        )

        assert config.max_attempts == 5
        assert config.initial_delay == 2.0
        assert config.max_delay == 120.0
        assert config.exponential_base == 3.0
        assert config.jitter is False

    def test_invalid_max_attempts(self):
        """Test validation of max_attempts"""
        with pytest.raises(ValueError, match="max_attempts must be >= 1"):
            RetryConfig(max_attempts=0)

    def test_invalid_initial_delay(self):
        """Test validation of initial_delay"""
        with pytest.raises(ValueError, match="initial_delay must be > 0"):
            RetryConfig(initial_delay=0)

    def test_invalid_max_delay(self):
        """Test validation of max_delay"""
        with pytest.raises(ValueError, match="max_delay must be >= initial_delay"):
            RetryConfig(initial_delay=10.0, max_delay=5.0)

    def test_invalid_exponential_base(self):
        """Test validation of exponential_base"""
        with pytest.raises(ValueError, match="exponential_base must be > 1"):
            RetryConfig(exponential_base=1.0)


class TestRetryStrategy:
    """Test retry strategy execution"""

    @pytest.mark.asyncio
    async def test_successful_first_attempt(self):
        """Test function succeeds on first attempt"""
        mock_func = AsyncMock(return_value="success")
        config = RetryConfig(max_attempts=3)
        strategy = RetryStrategy(config)

        result = await strategy.execute_with_retry(mock_func, "arg1", kwarg1="value1")

        assert result == "success"
        assert mock_func.call_count == 1
        mock_func.assert_called_once_with("arg1", kwarg1="value1")

    @pytest.mark.asyncio
    async def test_retry_on_retryable_error(self):
        """Test retry logic on retryable errors"""
        mock_func = AsyncMock()
        # Fail twice, then succeed
        mock_func.side_effect = [
            NetworkError("Connection failed"),
            NetworkError("Connection failed again"),
            "success"
        ]

        config = RetryConfig(max_attempts=3, initial_delay=0.01, jitter=False)
        strategy = RetryStrategy(config)

        result = await strategy.execute_with_retry(mock_func)

        assert result == "success"
        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        """Test behavior when max retries are exceeded"""
        mock_func = AsyncMock(side_effect=NetworkError("Always fails"))
        config = RetryConfig(max_attempts=3, initial_delay=0.01)
        strategy = RetryStrategy(config)

        with pytest.raises(NetworkError, match="Always fails"):
            await strategy.execute_with_retry(mock_func)

        assert mock_func.call_count == 3

    @pytest.mark.asyncio
    async def test_non_retryable_error_fails_immediately(self):
        """Test that non-retryable errors fail immediately"""
        mock_func = AsyncMock(side_effect=ValidationError("Invalid data"))
        config = RetryConfig(max_attempts=3)
        strategy = RetryStrategy(config)

        with pytest.raises(ValidationError, match="Invalid data"):
            await strategy.execute_with_retry(mock_func)

        # Should only be called once (no retries)
        assert mock_func.call_count == 1

    @pytest.mark.asyncio
    async def test_exponential_backoff(self):
        """Test exponential backoff delay calculation"""
        config = RetryConfig(
            max_attempts=4,
            initial_delay=1.0,
            exponential_base=2.0,
            jitter=False
        )
        strategy = RetryStrategy(config)

        # Test delay calculations
        assert strategy._calculate_delay(1) == 1.0  # 1.0 * 2^0
        assert strategy._calculate_delay(2) == 2.0  # 1.0 * 2^1
        assert strategy._calculate_delay(3) == 4.0  # 1.0 * 2^2
        assert strategy._calculate_delay(4) == 8.0  # 1.0 * 2^3

    @pytest.mark.asyncio
    async def test_max_delay_cap(self):
        """Test that delay is capped at max_delay"""
        config = RetryConfig(
            initial_delay=10.0,
            max_delay=20.0,
            exponential_base=2.0,
            jitter=False
        )
        strategy = RetryStrategy(config)

        # Would be 40.0 without cap
        delay = strategy._calculate_delay(3)
        assert delay == 20.0

    @pytest.mark.asyncio
    async def test_jitter_adds_randomness(self):
        """Test that jitter adds randomness to delays"""
        config = RetryConfig(
            initial_delay=10.0,
            jitter=True
        )
        strategy = RetryStrategy(config)

        # Calculate delay multiple times and check for variation
        delays = [strategy._calculate_delay(1) for _ in range(10)]

        # All delays should be >= 10.0 and <= 15.0 (10.0 + 50% jitter)
        assert all(10.0 <= d <= 15.0 for d in delays)

        # There should be variation (not all the same)
        assert len(set(delays)) > 1

    @pytest.mark.asyncio
    async def test_execute_with_timeout_and_retry(self):
        """Test combined timeout and retry logic"""
        mock_func = AsyncMock()

        # First call times out, second succeeds
        async def slow_then_fast():
            if mock_func.call_count == 1:
                await asyncio.sleep(2.0)  # Will timeout
            return "success"

        mock_func.side_effect = slow_then_fast

        config = RetryConfig(max_attempts=2, initial_delay=0.01)
        strategy = RetryStrategy(config)

        result = await strategy.execute_with_timeout_and_retry(
            mock_func,
            timeout=0.1
        )

        assert result == "success"
        assert mock_func.call_count == 2


class TestRetryDecorator:
    """Test retry decorator"""

    @pytest.mark.asyncio
    async def test_retry_decorator_success(self):
        """Test retry decorator on successful function"""
        call_count = 0

        @retry(max_attempts=3, initial_delay=0.01)
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise NetworkError("Fail")
            return "success"

        result = await test_func()

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_retry_decorator_stores_config(self):
        """Test that decorator stores config on function"""
        @retry(max_attempts=5, initial_delay=2.0)
        async def test_func():
            return "test"

        assert hasattr(test_func, '_retry_config')
        assert test_func._retry_config.max_attempts == 5
        assert test_func._retry_config.initial_delay == 2.0

    @pytest.mark.asyncio
    async def test_retry_with_timeout_decorator(self):
        """Test retry_with_timeout decorator"""
        call_count = 0

        @retry_with_timeout(
            timeout=1.0,
            max_attempts=2,
            initial_delay=0.01
        )
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                await asyncio.sleep(2.0)  # Will timeout
            return "success"

        result = await test_func()

        assert result == "success"
        assert call_count == 2
        assert hasattr(test_func, '_timeout')
        assert test_func._timeout == 1.0


class TestCircuitBreaker:
    """Test circuit breaker pattern"""

    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_state(self):
        """Test circuit breaker in CLOSED state (normal operation)"""
        mock_func = AsyncMock(return_value="success")
        breaker = CircuitBreaker(failure_threshold=3)

        result = await breaker.call(mock_func)

        assert result == "success"
        assert breaker.state == "CLOSED"
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self):
        """Test circuit breaker opens after threshold failures"""
        mock_func = AsyncMock(side_effect=Exception("Error"))
        breaker = CircuitBreaker(failure_threshold=3)

        # First 3 failures
        for i in range(3):
            with pytest.raises(Exception):
                await breaker.call(mock_func)

        assert breaker.state == "OPEN"
        assert breaker.failure_count == 3

        # Next call should fail immediately without calling function
        mock_func.reset_mock()
        with pytest.raises(CircuitBreakerOpenError):
            await breaker.call(mock_func)

        assert mock_func.call_count == 0  # Function was not called

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self):
        """Test circuit breaker recovery through HALF_OPEN state"""
        call_count = 0

        async def flaky_func():
            nonlocal call_count
            call_count += 1
            if call_count <= 3:
                raise Exception("Fail")
            return "success"

        breaker = CircuitBreaker(
            failure_threshold=3,
            recovery_timeout=0.1
        )

        # Trigger failures to open circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await breaker.call(flaky_func)

        assert breaker.state == "OPEN"

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Next call should transition to HALF_OPEN
        result = await breaker.call(flaky_func)

        assert result == "success"
        assert breaker.state == "CLOSED"
        assert breaker.failure_count == 0

    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_failure(self):
        """Test circuit breaker returns to OPEN if HALF_OPEN test fails"""
        mock_func = AsyncMock(side_effect=Exception("Error"))
        breaker = CircuitBreaker(
            failure_threshold=2,
            recovery_timeout=0.1
        )

        # Open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                await breaker.call(mock_func)

        assert breaker.state == "OPEN"

        # Wait for recovery timeout
        await asyncio.sleep(0.15)

        # Test call in HALF_OPEN fails
        with pytest.raises(Exception):
            await breaker.call(mock_func)

        # Circuit should remain OPEN
        assert breaker.state == "OPEN"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
