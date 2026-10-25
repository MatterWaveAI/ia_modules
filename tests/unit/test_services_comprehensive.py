"""
Comprehensive unit tests for pipeline services

Tests all methods and edge cases in ServiceRegistry and CentralLoggingService
"""

import pytest
from unittest.mock import Mock, AsyncMock
from datetime import datetime
import json

from ia_modules.pipeline.services import ServiceRegistry, CentralLoggingService, LogEntry


class TestLogEntry:
    """Test LogEntry class"""

    def test_log_entry_creation(self):
        """Test creating a log entry"""
        entry = LogEntry("INFO", "Test message", "test_step", {"key": "value"})

        assert entry.level == "INFO"
        assert entry.message == "Test message"
        assert entry.step_name == "test_step"
        assert entry.data == {"key": "value"}
        assert isinstance(entry.timestamp, datetime)

    def test_log_entry_without_optional_params(self):
        """Test log entry with minimal parameters"""
        entry = LogEntry("ERROR", "Error message")

        assert entry.level == "ERROR"
        assert entry.message == "Error message"
        assert entry.step_name is None
        assert entry.data == {}

    def test_log_entry_timestamp_set(self):
        """Test that timestamp is set on creation"""
        entry = LogEntry("INFO", "Test")

        assert entry.timestamp is not None
        assert isinstance(entry.timestamp, datetime)


class TestCentralLoggingService:
    """Test CentralLoggingService"""

    def test_init(self):
        """Test service initialization"""
        logger = CentralLoggingService()

        assert logger.execution_logs == []
        assert logger.current_execution_id is None

    def test_set_execution_id(self):
        """Test setting execution ID"""
        logger = CentralLoggingService()
        logger.set_execution_id("exec-123")

        assert logger.current_execution_id == "exec-123"

    def test_set_execution_id_multiple_times(self):
        """Test changing execution ID"""
        logger = CentralLoggingService()
        logger.set_execution_id("exec-1")
        logger.set_execution_id("exec-2")

        assert logger.current_execution_id == "exec-2"

    def test_log_basic(self):
        """Test basic logging"""
        logger = CentralLoggingService()
        logger.log("INFO", "Test message")

        assert len(logger.execution_logs) == 1
        assert logger.execution_logs[0].level == "INFO"
        assert logger.execution_logs[0].message == "Test message"

    def test_log_with_step_name(self):
        """Test logging with step name"""
        logger = CentralLoggingService()
        logger.log("INFO", "Test message", step_name="step1")

        assert logger.execution_logs[0].step_name == "step1"

    def test_log_with_data(self):
        """Test logging with additional data"""
        logger = CentralLoggingService()
        data = {"user": "test", "count": 42}
        logger.log("INFO", "Test message", data=data)

        assert logger.execution_logs[0].data == data

    def test_info_method(self):
        """Test info convenience method"""
        logger = CentralLoggingService()
        logger.info("Info message", "step1", {"key": "value"})

        assert len(logger.execution_logs) == 1
        assert logger.execution_logs[0].level == "INFO"
        assert logger.execution_logs[0].message == "Info message"

    def test_error_method(self):
        """Test error convenience method"""
        logger = CentralLoggingService()
        logger.error("Error message", "step1")

        assert logger.execution_logs[0].level == "ERROR"

    def test_warning_method(self):
        """Test warning convenience method"""
        logger = CentralLoggingService()
        logger.warning("Warning message")

        assert logger.execution_logs[0].level == "WARNING"

    def test_success_method(self):
        """Test success convenience method"""
        logger = CentralLoggingService()
        logger.success("Success message")

        assert logger.execution_logs[0].level == "SUCCESS"

    def test_multiple_logs(self):
        """Test logging multiple messages"""
        logger = CentralLoggingService()

        logger.info("Message 1")
        logger.error("Message 2")
        logger.warning("Message 3")

        assert len(logger.execution_logs) == 3
        assert logger.execution_logs[0].level == "INFO"
        assert logger.execution_logs[1].level == "ERROR"
        assert logger.execution_logs[2].level == "WARNING"

    def test_clear_logs(self):
        """Test clearing logs"""
        logger = CentralLoggingService()
        logger.set_execution_id("exec-123")
        logger.info("Message 1")
        logger.info("Message 2")

        logger.clear_logs()

        assert len(logger.execution_logs) == 0
        assert logger.current_execution_id is None

    @pytest.mark.asyncio
    async def test_write_to_database_success(self):
        """Test writing logs to database"""
        logger = CentralLoggingService()
        logger.set_execution_id("exec-123")
        logger.info("Test message", "step1", {"key": "value"})

        # Mock database service
        mock_db = Mock()
        mock_db.log_execution_event = AsyncMock()

        await logger.write_to_database(mock_db)

        # Verify database method was called
        mock_db.log_execution_event.assert_called_once()
        call_kwargs = mock_db.log_execution_event.call_args[1]
        assert call_kwargs['execution_id'] == "exec-123"
        assert call_kwargs['event_type'] == "INFO"
        assert call_kwargs['message'] == "Test message"
        assert call_kwargs['step_name'] == "step1"

    @pytest.mark.asyncio
    async def test_write_to_database_no_execution_id(self):
        """Test write to database without execution ID"""
        logger = CentralLoggingService()
        logger.info("Test message")

        mock_db = Mock()
        mock_db.log_execution_event = AsyncMock()

        await logger.write_to_database(mock_db)

        # Should not call database
        mock_db.log_execution_event.assert_not_called()

    @pytest.mark.asyncio
    async def test_write_to_database_no_db_service(self):
        """Test write to database without database service"""
        logger = CentralLoggingService()
        logger.set_execution_id("exec-123")
        logger.info("Test message")

        await logger.write_to_database(None)

        # Should not raise error
        assert True

    @pytest.mark.asyncio
    async def test_write_to_database_db_without_method(self):
        """Test write to database when db doesn't have log_execution_event"""
        logger = CentralLoggingService()
        logger.set_execution_id("exec-123")
        logger.info("Test message")

        mock_db = Mock(spec=[])  # No methods

        await logger.write_to_database(mock_db)

        # Should not raise error (silently skipped)
        assert True

    @pytest.mark.asyncio
    async def test_write_to_database_multiple_logs(self):
        """Test writing multiple logs to database"""
        logger = CentralLoggingService()
        logger.set_execution_id("exec-123")
        logger.info("Message 1")
        logger.error("Message 2")
        logger.success("Message 3")

        mock_db = Mock()
        mock_db.log_execution_event = AsyncMock()

        await logger.write_to_database(mock_db)

        # Should be called 3 times
        assert mock_db.log_execution_event.call_count == 3

    @pytest.mark.asyncio
    async def test_write_to_database_exception_handling(self):
        """Test that database exceptions are silently caught"""
        logger = CentralLoggingService()
        logger.set_execution_id("exec-123")
        logger.info("Test message")

        mock_db = Mock()
        mock_db.log_execution_event = AsyncMock(side_effect=Exception("DB error"))

        # Should not raise exception
        await logger.write_to_database(mock_db)

        assert True

    @pytest.mark.asyncio
    async def test_write_to_database_data_json_serialization(self):
        """Test that log data is JSON serialized"""
        logger = CentralLoggingService()
        logger.set_execution_id("exec-123")
        logger.info("Test", data={"key": "value", "count": 42})

        mock_db = Mock()
        mock_db.log_execution_event = AsyncMock()

        await logger.write_to_database(mock_db)

        call_kwargs = mock_db.log_execution_event.call_args[1]
        data = call_kwargs['data']
        # Should be JSON string
        assert isinstance(data, str)
        assert json.loads(data) == {"key": "value", "count": 42}


class TestServiceRegistry:
    """Test ServiceRegistry"""

    def test_init(self):
        """Test registry initialization"""
        registry = ServiceRegistry()

        assert isinstance(registry._services, dict)

    def test_init_creates_central_logger(self):
        """Test that registry creates central logger on init"""
        registry = ServiceRegistry()

        logger = registry.get("central_logger")
        assert logger is not None
        assert isinstance(logger, CentralLoggingService)

    def test_register_service(self):
        """Test registering a service"""
        registry = ServiceRegistry()
        mock_service = Mock()

        registry.register("test_service", mock_service)

        assert registry.get("test_service") == mock_service

    def test_register_multiple_services(self):
        """Test registering multiple services"""
        registry = ServiceRegistry()
        service1 = Mock()
        service2 = Mock()

        registry.register("service1", service1)
        registry.register("service2", service2)

        assert registry.get("service1") == service1
        assert registry.get("service2") == service2

    def test_register_overwrites_existing(self):
        """Test that registering same name overwrites"""
        registry = ServiceRegistry()
        service1 = Mock(name="first")
        service2 = Mock(name="second")

        registry.register("test", service1)
        registry.register("test", service2)

        assert registry.get("test") == service2

    def test_get_service(self):
        """Test getting a service"""
        registry = ServiceRegistry()
        mock_service = Mock()
        registry.register("test", mock_service)

        result = registry.get("test")

        assert result == mock_service

    def test_get_nonexistent_service(self):
        """Test getting non-existent service returns None"""
        registry = ServiceRegistry()

        result = registry.get("nonexistent")

        assert result is None

    def test_has_service_exists(self):
        """Test has() returns True for existing service"""
        registry = ServiceRegistry()
        registry.register("test", Mock())

        assert registry.has("test") is True

    def test_has_service_not_exists(self):
        """Test has() returns False for non-existent service"""
        registry = ServiceRegistry()

        assert registry.has("nonexistent") is False

    def test_has_central_logger_by_default(self):
        """Test that central_logger exists by default"""
        registry = ServiceRegistry()

        assert registry.has("central_logger") is True

    @pytest.mark.asyncio
    async def test_cleanup_all_with_cleanup_methods(self):
        """Test cleanup_all calls cleanup on services that have it"""
        registry = ServiceRegistry()

        # Create mock services with cleanup
        service1 = Mock()
        service1.cleanup = AsyncMock()
        service2 = Mock()
        service2.cleanup = AsyncMock()

        registry.register("service1", service1)
        registry.register("service2", service2)

        await registry.cleanup_all()

        service1.cleanup.assert_called_once()
        service2.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_all_without_cleanup_methods(self):
        """Test cleanup_all skips services without cleanup"""
        registry = ServiceRegistry()

        # Service without cleanup method
        service_no_cleanup = Mock(spec=[])
        registry.register("no_cleanup", service_no_cleanup)

        # Should not raise error
        await registry.cleanup_all()

        assert True

    @pytest.mark.asyncio
    async def test_cleanup_all_mixed_services(self):
        """Test cleanup_all with mix of services"""
        registry = ServiceRegistry()

        service_with = Mock()
        service_with.cleanup = AsyncMock()
        service_without = Mock(spec=[])

        registry.register("with", service_with)
        registry.register("without", service_without)

        await registry.cleanup_all()

        # Only service with cleanup should be called
        service_with.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_all_empty_registry(self):
        """Test cleanup_all with empty registry (only central_logger)"""
        registry = ServiceRegistry()

        # Should not raise error
        await registry.cleanup_all()

        assert True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
