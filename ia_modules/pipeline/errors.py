"""
Pipeline Error Classification System

Provides a comprehensive hierarchy of error types with severity levels
and categorization for proper error handling strategies.
"""

from enum import Enum
from typing import Optional, Dict, Any
from dataclasses import dataclass, field


class ErrorSeverity(Enum):
    """Error severity levels for pipeline execution"""
    CRITICAL = "critical"      # Pipeline must stop immediately
    ERROR = "error"            # Step fails but pipeline may continue
    WARNING = "warning"        # Issue logged but execution continues
    INFO = "info"              # Informational only, no action needed


class ErrorCategory(Enum):
    """Error categories for determining handling strategies"""
    NETWORK = "network"        # Network/connectivity errors (retryable)
    VALIDATION = "validation"  # Data validation failures (not retryable)
    TIMEOUT = "timeout"        # Execution timeouts (retryable)
    RESOURCE = "resource"      # Resource exhaustion - memory, disk, etc.
    DEPENDENCY = "dependency"  # External service failures (retryable)
    LOGIC = "logic"            # Business logic errors (not retryable)
    CONFIGURATION = "configuration"  # Configuration errors (not retryable)
    UNKNOWN = "unknown"        # Unclassified errors


@dataclass
class PipelineError(Exception):
    """Base error class for all pipeline errors"""
    message: str
    category: ErrorCategory
    severity: ErrorSeverity
    step_id: Optional[str] = None
    recoverable: bool = False
    context: Dict[str, Any] = field(default_factory=dict)
    original_exception: Optional[Exception] = None

    def __str__(self):
        parts = [
            f"[{self.severity.value.upper()}]",
            f"{self.category.value}:",
            self.message
        ]
        if self.step_id:
            parts.insert(1, f"Step '{self.step_id}'")
        return " ".join(parts)

    def __repr__(self):
        return (
            f"PipelineError(message={self.message!r}, "
            f"category={self.category}, severity={self.severity}, "
            f"step_id={self.step_id!r}, recoverable={self.recoverable})"
        )


# Network-related errors (typically retryable)
class NetworkError(PipelineError):
    """Network connectivity or HTTP errors"""

    def __init__(
        self,
        message: str,
        step_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.ERROR,
            step_id=step_id,
            recoverable=True,
            context=context or {},
            original_exception=original_exception
        )


class HTTPError(NetworkError):
    """HTTP-specific errors with status codes"""

    def __init__(
        self,
        message: str,
        status_code: int,
        step_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        context = context or {}
        context['status_code'] = status_code
        super().__init__(
            message=f"HTTP {status_code}: {message}",
            step_id=step_id,
            context=context,
            original_exception=original_exception
        )
        self.status_code = status_code


# Validation errors (not retryable)
class ValidationError(PipelineError):
    """Data validation or schema errors"""

    def __init__(
        self,
        message: str,
        step_id: Optional[str] = None,
        field: Optional[str] = None,
        expected_type: Optional[str] = None,
        actual_value: Any = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        context = context or {}
        if field:
            context['field'] = field
        if expected_type:
            context['expected_type'] = expected_type
        if actual_value is not None:
            context['actual_value'] = str(actual_value)

        super().__init__(
            message=message,
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.ERROR,
            step_id=step_id,
            recoverable=False,
            context=context,
            original_exception=original_exception
        )


# Timeout errors (retryable with caution)
class TimeoutError(PipelineError):
    """Execution timeout errors"""

    def __init__(
        self,
        message: str,
        timeout_seconds: float,
        step_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        context = context or {}
        context['timeout_seconds'] = timeout_seconds

        super().__init__(
            message=f"Timeout after {timeout_seconds}s: {message}",
            category=ErrorCategory.TIMEOUT,
            severity=ErrorSeverity.ERROR,
            step_id=step_id,
            recoverable=True,
            context=context,
            original_exception=original_exception
        )
        self.timeout_seconds = timeout_seconds


# Resource errors
class ResourceError(PipelineError):
    """Resource exhaustion errors (memory, disk, etc.)"""

    def __init__(
        self,
        message: str,
        resource_type: str,
        step_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        context = context or {}
        context['resource_type'] = resource_type

        super().__init__(
            message=f"{resource_type} resource error: {message}",
            category=ErrorCategory.RESOURCE,
            severity=ErrorSeverity.CRITICAL,
            step_id=step_id,
            recoverable=False,
            context=context,
            original_exception=original_exception
        )
        self.resource_type = resource_type


class MemoryError(ResourceError):
    """Memory exhaustion errors"""

    def __init__(
        self,
        message: str,
        step_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            resource_type="memory",
            step_id=step_id,
            context=context,
            original_exception=original_exception
        )


class DiskSpaceError(ResourceError):
    """Disk space exhaustion errors"""

    def __init__(
        self,
        message: str,
        step_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            resource_type="disk",
            step_id=step_id,
            context=context,
            original_exception=original_exception
        )


# Dependency errors (external service failures)
class DependencyError(PipelineError):
    """External dependency or service errors"""

    def __init__(
        self,
        message: str,
        service_name: str,
        step_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        context = context or {}
        context['service_name'] = service_name

        super().__init__(
            message=f"Dependency '{service_name}': {message}",
            category=ErrorCategory.DEPENDENCY,
            severity=ErrorSeverity.ERROR,
            step_id=step_id,
            recoverable=True,
            context=context,
            original_exception=original_exception
        )
        self.service_name = service_name


class DatabaseError(DependencyError):
    """Database-specific errors"""

    def __init__(
        self,
        message: str,
        step_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            service_name="database",
            step_id=step_id,
            context=context,
            original_exception=original_exception
        )


class APIError(DependencyError):
    """External API errors"""

    def __init__(
        self,
        message: str,
        api_name: str,
        step_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            service_name=api_name,
            step_id=step_id,
            context=context,
            original_exception=original_exception
        )


# Business logic errors
class LogicError(PipelineError):
    """Business logic or computation errors"""

    def __init__(
        self,
        message: str,
        step_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        super().__init__(
            message=message,
            category=ErrorCategory.LOGIC,
            severity=ErrorSeverity.ERROR,
            step_id=step_id,
            recoverable=False,
            context=context or {},
            original_exception=original_exception
        )


# Configuration errors
class ConfigurationError(PipelineError):
    """Configuration or setup errors"""

    def __init__(
        self,
        message: str,
        config_key: Optional[str] = None,
        step_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None
    ):
        context = context or {}
        if config_key:
            context['config_key'] = config_key

        super().__init__(
            message=message,
            category=ErrorCategory.CONFIGURATION,
            severity=ErrorSeverity.CRITICAL,
            step_id=step_id,
            recoverable=False,
            context=context,
            original_exception=original_exception
        )
        self.config_key = config_key


# Helper function to classify generic exceptions
def classify_exception(
    exception: Exception,
    step_id: Optional[str] = None,
    default_severity: ErrorSeverity = ErrorSeverity.ERROR
) -> PipelineError:
    """
    Classify a generic exception into a PipelineError

    Args:
        exception: The exception to classify
        step_id: Optional step ID where error occurred
        default_severity: Default severity if cannot be determined

    Returns:
        Appropriate PipelineError subclass
    """
    exc_type = type(exception).__name__
    message = str(exception)

    # Check for known exception types
    if 'timeout' in exc_type.lower() or 'timeout' in message.lower():
        return TimeoutError(
            message=message,
            timeout_seconds=0.0,  # Unknown timeout
            step_id=step_id,
            original_exception=exception
        )

    if any(keyword in exc_type.lower() for keyword in ['connection', 'network', 'http']):
        return NetworkError(
            message=message,
            step_id=step_id,
            original_exception=exception
        )

    if any(keyword in exc_type.lower() for keyword in ['validation', 'schema', 'type']):
        return ValidationError(
            message=message,
            step_id=step_id,
            original_exception=exception
        )

    if 'memory' in exc_type.lower():
        return MemoryError(
            message=message,
            step_id=step_id,
            original_exception=exception
        )

    # Check both exception type AND message for database/SQL keywords
    if (any(keyword in exc_type.lower() for keyword in ['database', 'sql']) or
        any(keyword in message.lower() for keyword in ['database', 'sql'])):
        return DatabaseError(
            message=message,
            step_id=step_id,
            original_exception=exception
        )

    # Default to generic PipelineError with UNKNOWN category
    return PipelineError(
        message=message,
        category=ErrorCategory.UNKNOWN,
        severity=default_severity,
        step_id=step_id,
        recoverable=False,
        context={'original_type': exc_type},
        original_exception=exception
    )
