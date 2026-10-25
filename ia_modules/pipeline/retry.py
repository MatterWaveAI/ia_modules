"""
Retry Strategy System

Provides exponential backoff retry logic for handling transient failures
in pipeline execution.
"""

from typing import Callable, Optional, Type, Tuple, Any
from dataclasses import dataclass
import asyncio
import logging
import random
import time
from functools import wraps

from .errors import PipelineError, NetworkError, TimeoutError, DependencyError


logger = logging.getLogger(__name__)


@dataclass
class RetryConfig:
    """Configuration for retry behavior"""
    max_attempts: int = 3
    initial_delay: float = 1.0
    max_delay: float = 60.0
    exponential_base: float = 2.0
    jitter: bool = True
    retryable_exceptions: Tuple[Type[Exception], ...] = (
        NetworkError,
        TimeoutError,
        DependencyError,
    )

    def __post_init__(self):
        """Validate configuration"""
        if self.max_attempts < 1:
            raise ValueError("max_attempts must be >= 1")
        if self.initial_delay <= 0:
            raise ValueError("initial_delay must be > 0")
        if self.max_delay < self.initial_delay:
            raise ValueError("max_delay must be >= initial_delay")
        if self.exponential_base <= 1:
            raise ValueError("exponential_base must be > 1")


class RetryStrategy:
    """Handles retry logic with exponential backoff and jitter"""

    def __init__(self, config: Optional[RetryConfig] = None):
        """
        Initialize retry strategy

        Args:
            config: Retry configuration. If None, uses defaults.
        """
        self.config = config or RetryConfig()
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def execute_with_retry(
        self,
        func: Callable,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute a function with retry logic

        Args:
            func: Async function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from successful function execution

        Raises:
            Exception: The last exception if all retries are exhausted
        """
        last_exception = None
        attempt = 0

        while attempt < self.config.max_attempts:
            attempt += 1

            try:
                # Execute the function
                self.logger.debug(
                    f"Attempting execution (attempt {attempt}/{self.config.max_attempts})"
                )
                result = await func(*args, **kwargs)

                # Success!
                if attempt > 1:
                    self.logger.info(
                        f"Execution succeeded on attempt {attempt}/{self.config.max_attempts}"
                    )
                return result

            except self.config.retryable_exceptions as e:
                last_exception = e

                # Check if we should retry
                if attempt >= self.config.max_attempts:
                    self.logger.error(
                        f"Max retries ({self.config.max_attempts}) exceeded. "
                        f"Last error: {e}"
                    )
                    raise

                # Calculate delay and wait
                delay = self._calculate_delay(attempt)
                self.logger.warning(
                    f"Attempt {attempt} failed with {type(e).__name__}: {e}. "
                    f"Retrying in {delay:.2f}s..."
                )

                # Record retry attempt if exception has context
                if isinstance(e, PipelineError) and hasattr(e, 'context'):
                    e.context['retry_attempt'] = attempt
                    e.context['retry_delay'] = delay

                await asyncio.sleep(delay)

            except Exception as e:
                # Non-retryable error - fail immediately
                self.logger.error(
                    f"Non-retryable error on attempt {attempt}: {type(e).__name__}: {e}"
                )
                raise

        # This should never be reached, but just in case
        if last_exception:
            raise last_exception
        raise RuntimeError("Retry logic failed unexpectedly")

    def _calculate_delay(self, attempt: int) -> float:
        """
        Calculate delay for retry with exponential backoff and optional jitter

        Args:
            attempt: Current attempt number (1-based)

        Returns:
            Delay in seconds
        """
        # Calculate exponential backoff
        delay = min(
            self.config.initial_delay * (self.config.exponential_base ** (attempt - 1)),
            self.config.max_delay
        )

        # Add jitter if enabled
        if self.config.jitter:
            # Add random jitter between 0% and 50% of delay
            jitter_amount = delay * random.uniform(0, 0.5)
            delay += jitter_amount

        return delay

    async def execute_with_timeout_and_retry(
        self,
        func: Callable,
        timeout: float,
        *args,
        **kwargs
    ) -> Any:
        """
        Execute function with both timeout and retry logic

        Args:
            func: Async function to execute
            timeout: Timeout in seconds for each attempt
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result from successful function execution

        Raises:
            TimeoutError: If function times out on all retries
            Exception: Other exceptions from the function
        """
        async def wrapped_func():
            """Wrapper that adds timeout"""
            try:
                return await asyncio.wait_for(func(*args, **kwargs), timeout=timeout)
            except asyncio.TimeoutError:
                from .errors import TimeoutError as PipelineTimeoutError
                raise PipelineTimeoutError(
                    message=f"Function exceeded timeout of {timeout}s",
                    timeout_seconds=timeout
                )

        return await self.execute_with_retry(wrapped_func)


def retry(
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None
):
    """
    Decorator for adding retry logic to async functions

    Args:
        max_attempts: Maximum number of attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to delays
        retryable_exceptions: Tuple of exception types to retry on

    Example:
        @retry(max_attempts=5, initial_delay=2.0)
        async def fetch_data():
            # This will retry up to 5 times with exponential backoff
            response = await http_client.get(url)
            return response.json()
    """
    retry_config = RetryConfig(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        retryable_exceptions=retryable_exceptions or RetryConfig.retryable_exceptions
    )
    strategy = RetryStrategy(retry_config)

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await strategy.execute_with_retry(func, *args, **kwargs)

        # Store retry config on function for introspection
        wrapper._retry_config = retry_config

        return wrapper

    return decorator


def retry_with_timeout(
    timeout: float,
    max_attempts: int = 3,
    initial_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2.0,
    jitter: bool = True,
    retryable_exceptions: Optional[Tuple[Type[Exception], ...]] = None
):
    """
    Decorator for adding both timeout and retry logic to async functions

    Args:
        timeout: Timeout in seconds for each attempt
        max_attempts: Maximum number of attempts
        initial_delay: Initial delay between retries in seconds
        max_delay: Maximum delay between retries in seconds
        exponential_base: Base for exponential backoff calculation
        jitter: Whether to add random jitter to delays
        retryable_exceptions: Tuple of exception types to retry on

    Example:
        @retry_with_timeout(timeout=30.0, max_attempts=3)
        async def slow_api_call():
            # Each attempt has 30s timeout, will retry up to 3 times
            response = await external_api.fetch()
            return response
    """
    retry_config = RetryConfig(
        max_attempts=max_attempts,
        initial_delay=initial_delay,
        max_delay=max_delay,
        exponential_base=exponential_base,
        jitter=jitter,
        retryable_exceptions=retryable_exceptions or RetryConfig.retryable_exceptions
    )
    strategy = RetryStrategy(retry_config)

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            return await strategy.execute_with_timeout_and_retry(
                func, timeout, *args, **kwargs
            )

        # Store config on function for introspection
        wrapper._retry_config = retry_config
        wrapper._timeout = timeout

        return wrapper

    return decorator


class CircuitBreaker:
    """
    Circuit breaker pattern to prevent cascading failures

    States:
        CLOSED: Normal operation, requests go through
        OPEN: Requests fail immediately without calling the function
        HALF_OPEN: Test request to check if service recovered
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    ):
        """
        Initialize circuit breaker

        Args:
            failure_threshold: Number of failures before opening circuit
            recovery_timeout: Seconds to wait before attempting recovery
            expected_exceptions: Exception types that trigger the circuit
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exceptions = expected_exceptions

        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.logger = logging.getLogger(f"{__name__}.CircuitBreaker")

    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function through circuit breaker

        Args:
            func: Async function to call
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Result from function

        Raises:
            CircuitBreakerOpenError: If circuit is open
            Exception: From the wrapped function
        """
        # Check if circuit should transition to HALF_OPEN
        if self.state == "OPEN":
            if (time.time() - self.last_failure_time) > self.recovery_timeout:
                self.logger.info("Circuit transitioning to HALF_OPEN for test")
                self.state = "HALF_OPEN"
            else:
                raise CircuitBreakerOpenError(
                    f"Circuit breaker is OPEN. "
                    f"Waiting {self.recovery_timeout}s for recovery."
                )

        try:
            result = await func(*args, **kwargs)

            # Success! Reset circuit if it was HALF_OPEN
            if self.state == "HALF_OPEN":
                self.logger.info("Circuit recovered, transitioning to CLOSED")
                self.state = "CLOSED"
                self.failure_count = 0

            return result

        except self.expected_exceptions:
            self.failure_count += 1
            self.last_failure_time = time.time()

            # Open circuit if threshold exceeded
            if self.failure_count >= self.failure_threshold:
                if self.state != "OPEN":
                    self.logger.error(
                        f"Circuit OPEN after {self.failure_count} failures"
                    )
                    self.state = "OPEN"

            raise


class CircuitBreakerOpenError(Exception):
    """Raised when circuit breaker is open"""
    pass
