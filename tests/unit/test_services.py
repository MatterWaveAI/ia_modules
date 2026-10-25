"""
Unit tests for service system
"""

from unittest.mock import Mock

import pytest

from ia_modules.pipeline.services import ServiceRegistry, CentralLoggingService


def test_central_logging_service():
    """Test central logging service functionality"""
    logger = CentralLoggingService()
    
    # Test setting execution ID
    logger.set_execution_id("test_exec_123")
    assert logger.current_execution_id == "test_exec_123"
    
    # Test logging messages
    logger.info("Test info message", "test_step")
    logger.error("Test error message", "test_step")
    logger.warning("Test warning message", "test_step")
    logger.success("Test success message", "test_step")
    
    # Test that logs were collected
    assert len(logger.execution_logs) == 4
    
    # Test clearing logs
    logger.clear_logs()
    assert len(logger.execution_logs) == 0
    assert logger.current_execution_id is None


def test_service_registry():
    """Test service registry functionality"""
    registry = ServiceRegistry()
    
    # Test registering and getting services
    mock_service = Mock()
    registry.register("test_service", mock_service)
    
    retrieved_service = registry.get("test_service")
    assert retrieved_service == mock_service
    
    # Test checking if service exists
    assert registry.has("test_service") is True
    assert registry.has("nonexistent_service") is False


def test_service_registry_with_central_logger():
    """Test that registry initializes with central logger"""
    registry = ServiceRegistry()
    
    logger = registry.get("central_logger")
    assert logger is not None
    assert isinstance(logger, CentralLoggingService)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
