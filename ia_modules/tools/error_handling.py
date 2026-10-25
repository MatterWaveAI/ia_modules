"""
Error handling strategies for tool execution.

Provides retry logic, fallback mechanisms, and circuit breaker pattern
for robust tool execution.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Callable, Optional, List
from functools import wraps


class RetryStrategy(Enum):
    """Retry strategy types."""
    EXPONENTIAL_BACKOFF = "exponential_backoff"
    LINEAR_BACKOFF = "linear_backoff"
    FIXED_DELAY = "fixed_delay"
    IMMEDIATE = "immediate"


@dataclass
class RetryConfig:
    """
    Configuration for retry behavior.

    Attributes:
        max_attempts: Maximum number of retry attempts
        strategy: Retry strategy to use
        initial_delay: Initial delay in seconds
        max_delay: Maximum delay in seconds
        backoff_multiplier: Multiplier for exponential backoff
        retryable_exceptions: Exception types that should trigger retry
        on_retry: Optional callback called before each retry
    """
    max_attempts: int = 3
    strategy: RetryStrategy = RetryStrategy.EXPONENTIAL_BACKOFF
    initial_delay: float = 1.0
    max_delay: float = 60.0
    backoff_multiplier: float = 2.0
    retryable_exceptions: tuple[type[Exception], ...] = (Exception,)
    on_retry: Optional[Callable[[int, Exception], None]] = None


@dataclass
class CircuitBreakerConfig:
    """
    Configuration for circuit breaker pattern.

    Attributes:
        failure_threshold: Number of failures before opening circuit
        success_threshold: Number of successes to close circuit
        timeout: Time in seconds before attempting to close circuit
        half_open_max_calls: Max calls allowed in half-open state
    """
    failure_threshold: int = 5
    success_threshold: int = 2
    timeout: float = 60.0
    half_open_max_calls: int = 1


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject calls
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""
    pass


class CircuitBreaker:
    """
    Circuit breaker pattern implementation.

    Prevents cascading failures by temporarily blocking calls to failing services.

    States:
    - CLOSED: Normal operation, calls allowed
    - OPEN: Too many failures, calls blocked
    - HALF_OPEN: Testing recovery, limited calls allowed

    Example:
        >>> breaker = CircuitBreaker()
        >>> async def risky_operation():
        ...     # May fail
        ...     return await external_api_call()
        >>>
        >>> result = await breaker.call(risky_operation)
    """

    def __init__(self, config: Optional[CircuitBreakerConfig] = None):
        """
        Initialize circuit breaker.

        Args:
            config: Circuit breaker configuration
        """
        self.config = config or CircuitBreakerConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self.half_open_calls = 0
        self.logger = logging.getLogger("CircuitBreaker")

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.

        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            CircuitBreakerError: If circuit is open
        """
        if self.state == CircuitState.OPEN:
            if self._should_attempt_reset():
                self.logger.info("Circuit breaker entering half-open state")
                self.state = CircuitState.HALF_OPEN
                self.half_open_calls = 0
            else:
                raise CircuitBreakerError("Circuit breaker is open")

        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_calls >= self.config.half_open_max_calls:
                raise CircuitBreakerError("Circuit breaker half-open limit reached")
            self.half_open_calls += 1

        try:
            result = await func(*args, **kwargs)
            self._on_success()
            return result
        except Exception:
            self._on_failure()
            raise

    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to attempt reset."""
        if self.last_failure_time is None:
            return True

        elapsed = (datetime.now(timezone.utc) - self.last_failure_time).total_seconds()
        return elapsed >= self.config.timeout

    def _on_success(self) -> None:
        """Handle successful call."""
        self.failure_count = 0

        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.config.success_threshold:
                self.logger.info("Circuit breaker closing after successful recovery")
                self.state = CircuitState.CLOSED
                self.success_count = 0

    def _on_failure(self) -> None:
        """Handle failed call."""
        self.failure_count += 1
        self.last_failure_time = datetime.now(timezone.utc)
        self.success_count = 0

        if self.failure_count >= self.config.failure_threshold:
            self.logger.warning(f"Circuit breaker opening after {self.failure_count} failures")
            self.state = CircuitState.OPEN

    def reset(self) -> None:
        """Manually reset circuit breaker to closed state."""
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None
        self.logger.info("Circuit breaker manually reset")


class RetryExecutor:
    """
    Executes functions with configurable retry logic.

    Supports multiple retry strategies and exception handling.

    Example:
        >>> executor = RetryExecutor(RetryConfig(max_attempts=5))
        >>> result = await executor.execute(flaky_function, arg1, arg2)
    """

    def __init__(self, config: Optional[RetryConfig] = None):
        """
        Initialize retry executor.

        Args:
            config: Retry configuration
        """
        self.config = config or RetryConfig()
        self.logger = logging.getLogger("RetryExecutor")

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with retry logic.

        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If all retry attempts fail
        """
        last_exception = None

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                return await func(*args, **kwargs)
            except self.config.retryable_exceptions as e:
                last_exception = e

                if attempt == self.config.max_attempts:
                    self.logger.error(f"All {self.config.max_attempts} attempts failed")
                    raise

                delay = self._calculate_delay(attempt)
                self.logger.warning(
                    f"Attempt {attempt}/{self.config.max_attempts} failed: {e}. "
                    f"Retrying in {delay:.2f}s"
                )

                if self.config.on_retry:
                    self.config.on_retry(attempt, e)

                await asyncio.sleep(delay)

        # Should never reach here, but just in case
        assert last_exception is not None
        raise last_exception

    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate retry delay based on strategy.

        Args:
            attempt: Current attempt number (1-indexed)

        Returns:
            Delay in seconds
        """
        if self.config.strategy == RetryStrategy.IMMEDIATE:
            return 0

        elif self.config.strategy == RetryStrategy.FIXED_DELAY:
            return min(self.config.initial_delay, self.config.max_delay)

        elif self.config.strategy == RetryStrategy.LINEAR_BACKOFF:
            delay = self.config.initial_delay * attempt
            return min(delay, self.config.max_delay)

        elif self.config.strategy == RetryStrategy.EXPONENTIAL_BACKOFF:
            delay = self.config.initial_delay * (self.config.backoff_multiplier ** (attempt - 1))
            return min(delay, self.config.max_delay)

        return self.config.initial_delay


@dataclass
class FallbackConfig:
    """
    Configuration for fallback behavior.

    Attributes:
        fallback_functions: List of fallback functions to try in order
        fallback_on_exceptions: Exception types that trigger fallback
        return_default_on_all_failures: Whether to return default value if all fail
        default_value: Default value to return
    """
    fallback_functions: List[Callable] = field(default_factory=list)
    fallback_on_exceptions: tuple[type[Exception], ...] = (Exception,)
    return_default_on_all_failures: bool = False
    default_value: Any = None


class FallbackExecutor:
    """
    Executes functions with fallback chain.

    If primary function fails, tries fallback functions in order.

    Example:
        >>> async def primary(): ...
        >>> async def fallback1(): ...
        >>> async def fallback2(): ...
        >>>
        >>> executor = FallbackExecutor(FallbackConfig(
        ...     fallback_functions=[fallback1, fallback2]
        ... ))
        >>> result = await executor.execute(primary, arg1, arg2)
    """

    def __init__(self, config: Optional[FallbackConfig] = None):
        """
        Initialize fallback executor.

        Args:
            config: Fallback configuration
        """
        self.config = config or FallbackConfig()
        self.logger = logging.getLogger("FallbackExecutor")

    async def execute(self, primary_func: Callable, *args, **kwargs) -> Any:
        """
        Execute primary function with fallback chain.

        Args:
            primary_func: Primary async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If all functions fail and no default value
        """
        functions = [primary_func] + self.config.fallback_functions
        last_exception = None

        for i, func in enumerate(functions):
            try:
                func_name = func.__name__ if hasattr(func, '__name__') else str(func)
                if i == 0:
                    self.logger.debug(f"Executing primary function: {func_name}")
                else:
                    self.logger.info(f"Trying fallback {i}: {func_name}")

                return await func(*args, **kwargs)

            except self.config.fallback_on_exceptions as e:
                last_exception = e
                func_name = func.__name__ if hasattr(func, '__name__') else str(func)
                self.logger.warning(f"Function {func_name} failed: {e}")
                continue

        # All functions failed
        if self.config.return_default_on_all_failures:
            self.logger.warning("All functions failed, returning default value")
            return self.config.default_value

        assert last_exception is not None
        raise last_exception


class CompositeErrorHandler:
    """
    Combines retry, circuit breaker, and fallback strategies.

    Provides comprehensive error handling for tool execution.

    Example:
        >>> handler = CompositeErrorHandler(
        ...     retry_config=RetryConfig(max_attempts=3),
        ...     circuit_breaker_config=CircuitBreakerConfig(),
        ...     fallback_config=FallbackConfig(fallback_functions=[backup_func])
        ... )
        >>> result = await handler.execute(main_func, arg1, arg2)
    """

    def __init__(
        self,
        retry_config: Optional[RetryConfig] = None,
        circuit_breaker_config: Optional[CircuitBreakerConfig] = None,
        fallback_config: Optional[FallbackConfig] = None
    ):
        """
        Initialize composite error handler.

        Args:
            retry_config: Retry configuration
            circuit_breaker_config: Circuit breaker configuration
            fallback_config: Fallback configuration
        """
        self.retry_executor = RetryExecutor(retry_config) if retry_config else None
        self.circuit_breaker = CircuitBreaker(circuit_breaker_config) if circuit_breaker_config else None
        self.fallback_executor = FallbackExecutor(fallback_config) if fallback_config else None
        self.logger = logging.getLogger("CompositeErrorHandler")

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with full error handling.

        Applies circuit breaker, retry, and fallback in that order.

        Args:
            func: Async function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result
        """
        async def wrapped_func(*a, **kw):
            # Apply retry if configured
            if self.retry_executor:
                return await self.retry_executor.execute(func, *a, **kw)
            else:
                return await func(*a, **kw)

        # Apply circuit breaker if configured
        if self.circuit_breaker:
            try:
                return await self.circuit_breaker.call(wrapped_func, *args, **kwargs)
            except (CircuitBreakerError, Exception):
                # Circuit breaker open or function failed
                if self.fallback_executor and self.fallback_executor.config.fallback_functions:
                    self.logger.info("Primary function failed, trying fallback chain")
                    return await self.fallback_executor.execute(func, *args, **kwargs)
                raise

        # Apply fallback if configured and no circuit breaker
        elif self.fallback_executor and self.fallback_executor.config.fallback_functions:
            return await self.fallback_executor.execute(wrapped_func, *args, **kwargs)

        # No error handling configured, just retry
        elif self.retry_executor:
            return await self.retry_executor.execute(func, *args, **kwargs)

        # No error handling at all
        else:
            return await func(*args, **kwargs)


def with_retry(config: Optional[RetryConfig] = None):
    """
    Decorator for adding retry logic to async functions.

    Args:
        config: Retry configuration

    Example:
        >>> @with_retry(RetryConfig(max_attempts=5))
        ... async def fetch_data():
        ...     return await api_call()
    """
    executor = RetryExecutor(config)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await executor.execute(func, *args, **kwargs)
        return wrapper
    return decorator


def with_circuit_breaker(config: Optional[CircuitBreakerConfig] = None):
    """
    Decorator for adding circuit breaker to async functions.

    Args:
        config: Circuit breaker configuration

    Example:
        >>> @with_circuit_breaker(CircuitBreakerConfig())
        ... async def external_api():
        ...     return await make_request()
    """
    breaker = CircuitBreaker(config)

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await breaker.call(func, *args, **kwargs)
        return wrapper
    return decorator


def with_fallback(fallback_func: Callable, default_value: Any = None):
    """
    Decorator for adding fallback to async functions.

    Args:
        fallback_func: Fallback function to use
        default_value: Default value if both fail

    Example:
        >>> async def backup_source():
        ...     return "backup data"
        >>>
        >>> @with_fallback(backup_source)
        ... async def primary_source():
        ...     return await fetch_from_primary()
    """
    executor = FallbackExecutor(FallbackConfig(
        fallback_functions=[fallback_func],
        return_default_on_all_failures=default_value is not None,
        default_value=default_value
    ))

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await executor.execute(func, *args, **kwargs)
        return wrapper
    return decorator
