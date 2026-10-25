"""
Unit tests for error classification system
"""

import pytest
from ia_modules.pipeline.errors import (
    PipelineError,
    ErrorSeverity,
    ErrorCategory,
    NetworkError,
    HTTPError,
    ValidationError,
    TimeoutError,
    ResourceError,
    MemoryError,
    DiskSpaceError,
    DependencyError,
    DatabaseError,
    APIError,
    LogicError,
    ConfigurationError,
    classify_exception
)


class TestErrorSeverity:
    """Test error severity levels"""

    def test_severity_values(self):
        """Test all severity levels have correct values"""
        assert ErrorSeverity.CRITICAL.value == "critical"
        assert ErrorSeverity.ERROR.value == "error"
        assert ErrorSeverity.WARNING.value == "warning"
        assert ErrorSeverity.INFO.value == "info"


class TestErrorCategory:
    """Test error categories"""

    def test_category_values(self):
        """Test all categories have correct values"""
        assert ErrorCategory.NETWORK.value == "network"
        assert ErrorCategory.VALIDATION.value == "validation"
        assert ErrorCategory.TIMEOUT.value == "timeout"
        assert ErrorCategory.RESOURCE.value == "resource"
        assert ErrorCategory.DEPENDENCY.value == "dependency"
        assert ErrorCategory.LOGIC.value == "logic"
        assert ErrorCategory.CONFIGURATION.value == "configuration"
        assert ErrorCategory.UNKNOWN.value == "unknown"


class TestPipelineError:
    """Test base PipelineError class"""

    def test_pipeline_error_creation(self):
        """Test creating a basic pipeline error"""
        error = PipelineError(
            message="Test error",
            category=ErrorCategory.LOGIC,
            severity=ErrorSeverity.ERROR,
            step_id="test_step",
            recoverable=False
        )

        assert error.message == "Test error"
        assert error.category == ErrorCategory.LOGIC
        assert error.severity == ErrorSeverity.ERROR
        assert error.step_id == "test_step"
        assert error.recoverable is False
        assert error.context == {}

    def test_pipeline_error_with_context(self):
        """Test error with context data"""
        context = {"key": "value", "count": 42}
        error = PipelineError(
            message="Test error",
            category=ErrorCategory.UNKNOWN,
            severity=ErrorSeverity.ERROR,
            context=context
        )

        assert error.context == context
        assert error.context["key"] == "value"
        assert error.context["count"] == 42

    def test_pipeline_error_str(self):
        """Test error string representation"""
        error = PipelineError(
            message="Something went wrong",
            category=ErrorCategory.VALIDATION,
            severity=ErrorSeverity.ERROR,
            step_id="validator"
        )

        error_str = str(error)
        assert "[ERROR]" in error_str
        assert "validation:" in error_str
        assert "Something went wrong" in error_str
        assert "validator" in error_str

    def test_pipeline_error_repr(self):
        """Test error repr"""
        error = PipelineError(
            message="Test",
            category=ErrorCategory.NETWORK,
            severity=ErrorSeverity.WARNING
        )

        repr_str = repr(error)
        assert "PipelineError" in repr_str
        assert "message='Test'" in repr_str
        assert "category=ErrorCategory.NETWORK" in repr_str


class TestNetworkError:
    """Test network error types"""

    def test_network_error_defaults(self):
        """Test NetworkError has correct defaults"""
        error = NetworkError(message="Connection failed")

        assert error.category == ErrorCategory.NETWORK
        assert error.severity == ErrorSeverity.ERROR
        assert error.recoverable is True
        assert error.message == "Connection failed"

    def test_network_error_with_step_id(self):
        """Test NetworkError with step ID"""
        error = NetworkError(
            message="Request timeout",
            step_id="api_call"
        )

        assert error.step_id == "api_call"
        assert "api_call" in str(error)

    def test_network_error_with_original_exception(self):
        """Test NetworkError wrapping original exception"""
        original = Exception("Original error")
        error = NetworkError(
            message="Wrapped error",
            original_exception=original
        )

        assert error.original_exception is original


class TestHTTPError:
    """Test HTTP error types"""

    def test_http_error_creation(self):
        """Test HTTPError with status code"""
        error = HTTPError(
            message="Not found",
            status_code=404
        )

        assert error.status_code == 404
        assert "HTTP 404" in error.message
        assert "Not found" in error.message
        assert error.context["status_code"] == 404

    def test_http_error_different_codes(self):
        """Test different HTTP status codes"""
        # 500 error
        error_500 = HTTPError(message="Server error", status_code=500)
        assert error_500.status_code == 500
        assert "500" in error_500.message

        # 403 error
        error_403 = HTTPError(message="Forbidden", status_code=403)
        assert error_403.status_code == 403
        assert "403" in error_403.message


class TestValidationError:
    """Test validation error types"""

    def test_validation_error_defaults(self):
        """Test ValidationError has correct defaults"""
        error = ValidationError(message="Invalid data")

        assert error.category == ErrorCategory.VALIDATION
        assert error.severity == ErrorSeverity.ERROR
        assert error.recoverable is False

    def test_validation_error_with_field_info(self):
        """Test ValidationError with field information"""
        error = ValidationError(
            message="Invalid type",
            field="age",
            expected_type="int",
            actual_value="not a number"
        )

        assert error.context["field"] == "age"
        assert error.context["expected_type"] == "int"
        assert error.context["actual_value"] == "not a number"


class TestTimeoutError:
    """Test timeout error types"""

    def test_timeout_error_creation(self):
        """Test TimeoutError with timeout value"""
        error = TimeoutError(
            message="Operation timed out",
            timeout_seconds=30.0
        )

        assert error.timeout_seconds == 30.0
        assert "30.0s" in error.message
        assert error.category == ErrorCategory.TIMEOUT
        assert error.recoverable is True


class TestResourceErrors:
    """Test resource error types"""

    def test_resource_error_creation(self):
        """Test ResourceError with resource type"""
        error = ResourceError(
            message="Resource exhausted",
            resource_type="cpu"
        )

        assert error.resource_type == "cpu"
        assert "cpu" in error.message
        assert error.category == ErrorCategory.RESOURCE
        assert error.severity == ErrorSeverity.CRITICAL

    def test_memory_error(self):
        """Test MemoryError subclass"""
        error = MemoryError(message="Out of memory")

        assert error.resource_type == "memory"
        assert "memory" in error.message

    def test_disk_space_error(self):
        """Test DiskSpaceError subclass"""
        error = DiskSpaceError(message="Disk full")

        assert error.resource_type == "disk"
        assert "disk" in error.message


class TestDependencyErrors:
    """Test dependency error types"""

    def test_dependency_error_creation(self):
        """Test DependencyError with service name"""
        error = DependencyError(
            message="Service unavailable",
            service_name="auth_service"
        )

        assert error.service_name == "auth_service"
        assert "auth_service" in error.message
        assert error.category == ErrorCategory.DEPENDENCY
        assert error.recoverable is True

    def test_database_error(self):
        """Test DatabaseError subclass"""
        error = DatabaseError(message="Connection failed")

        assert error.service_name == "database"
        assert error.category == ErrorCategory.DEPENDENCY

    def test_api_error(self):
        """Test APIError subclass"""
        error = APIError(
            message="Request failed",
            api_name="google_maps"
        )

        assert error.service_name == "google_maps"
        assert "google_maps" in error.message


class TestLogicError:
    """Test logic error types"""

    def test_logic_error_defaults(self):
        """Test LogicError has correct defaults"""
        error = LogicError(message="Business rule violated")

        assert error.category == ErrorCategory.LOGIC
        assert error.severity == ErrorSeverity.ERROR
        assert error.recoverable is False


class TestConfigurationError:
    """Test configuration error types"""

    def test_configuration_error_creation(self):
        """Test ConfigurationError"""
        error = ConfigurationError(
            message="Missing required config",
            config_key="api_key"
        )

        assert error.config_key == "api_key"
        assert error.context["config_key"] == "api_key"
        assert error.category == ErrorCategory.CONFIGURATION
        assert error.severity == ErrorSeverity.CRITICAL


class TestClassifyException:
    """Test exception classification"""

    def test_classify_timeout_exception(self):
        """Test classifying timeout exceptions"""
        exc = Exception("Connection timeout occurred")
        classified = classify_exception(exc, step_id="test")

        assert isinstance(classified, TimeoutError)
        assert classified.step_id == "test"
        assert classified.category == ErrorCategory.TIMEOUT

    def test_classify_network_exception(self):
        """Test classifying network exceptions"""
        exc = ConnectionError("Network unreachable")
        classified = classify_exception(exc)

        assert isinstance(classified, NetworkError)
        assert classified.category == ErrorCategory.NETWORK

    def test_classify_validation_exception(self):
        """Test classifying validation exceptions"""
        exc = TypeError("Invalid type for field")
        classified = classify_exception(exc)

        assert isinstance(classified, ValidationError)
        assert classified.category == ErrorCategory.VALIDATION

    def test_classify_memory_exception(self):
        """Test classifying memory exceptions"""
        exc = MemoryError("Out of memory")
        classified = classify_exception(exc)

        assert isinstance(classified, MemoryError)
        assert classified.category == ErrorCategory.RESOURCE

    def test_classify_database_exception(self):
        """Test classifying database exceptions"""
        exc = Exception("SQL syntax error")
        classified = classify_exception(exc)

        assert isinstance(classified, DatabaseError)
        assert classified.category == ErrorCategory.DEPENDENCY

    def test_classify_unknown_exception(self):
        """Test classifying unknown exceptions"""
        exc = ValueError("Some random error")
        classified = classify_exception(exc, step_id="unknown_step")

        assert isinstance(classified, PipelineError)
        assert classified.category == ErrorCategory.UNKNOWN
        assert classified.step_id == "unknown_step"
        assert classified.context["original_type"] == "ValueError"
        assert classified.original_exception is exc

    def test_classify_with_custom_severity(self):
        """Test classifying with custom severity"""
        exc = Exception("Test")
        classified = classify_exception(
            exc,
            default_severity=ErrorSeverity.WARNING
        )

        assert classified.severity == ErrorSeverity.WARNING


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
