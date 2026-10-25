"""
Integration tests for service system with real service interactions
"""

import asyncio

import pytest

from ia_modules.pipeline.services import ServiceRegistry


class MockService:
    """Mock service for integration testing"""
    
    def __init__(self, name: str):
        self.name = name
        self.started = False
    
    async def start(self):
        self.started = True
        return f"{self.name} started"
    
    async def stop(self):
        self.started = False
        return f"{self.name} stopped"
    
    def get_status(self):
        return {"name": self.name, "started": self.started}


@pytest.mark.asyncio
async def test_service_registry_lifecycle():
    """Test complete service lifecycle management"""
    registry = ServiceRegistry()
    
    # Register multiple services
    service1 = MockService("service1")
    service2 = MockService("service2")
    
    registry.register("test_service1", service1)
    registry.register("test_service2", service2)
    
    # Verify services are registered
    assert registry.has("test_service1")
    assert registry.has("test_service2")
    
    # Get services and test them
    retrieved1 = registry.get("test_service1")
    retrieved2 = registry.get("test_service2")
    
    assert retrieved1 == service1
    assert retrieved2 == service2
    
    # Test service operations
    await retrieved1.start()
    await retrieved2.start()
    
    assert retrieved1.started is True
    assert retrieved2.started is True


@pytest.mark.asyncio
async def test_service_dependency_resolution():
    """Test service dependency resolution"""
    registry = ServiceRegistry()
    
    # Create services with dependencies
    primary_service = MockService("primary")
    dependent_service = MockService("dependent")
    
    # Register services
    registry.register("primary_service", primary_service)
    registry.register("dependent_service", dependent_service)
    
    # Simulate dependency injection
    class DependentService:
        def __init__(self, primary_service):
            self.primary_service = primary_service
            self.name = "dependent_with_injection"
        
        async def start(self):
            # Start dependency first
            await self.primary_service.start()
            return f"Started with dependency: {self.primary_service.name}"
    
    # Create dependent service with injection
    dependent_with_injection = DependentService(registry.get("primary_service"))
    registry.register("dependent_with_injection", dependent_with_injection)
    
    # Test dependency resolution
    result = await dependent_with_injection.start()
    assert "Started with dependency: primary" in result
    assert registry.get("primary_service").started is True


@pytest.mark.asyncio
async def test_central_logging_cross_service():
    """Test central logging across multiple services"""
    registry = ServiceRegistry()
    logger = registry.get("central_logger")
    
    # Set execution context
    execution_id = "test_exec_integration_456"
    logger.set_execution_id(execution_id)
    
    # Simulate multiple services logging
    class ServiceA:
        def __init__(self, logger):
            self.logger = logger
        
        async def do_work(self):
            self.logger.info("ServiceA starting work", "service_a")
            await asyncio.sleep(0.01)  # Simulate work
            self.logger.success("ServiceA completed work", "service_a")
            return "work_done"
    
    class ServiceB:
        def __init__(self, logger):
            self.logger = logger
        
        async def do_work(self):
            self.logger.info("ServiceB starting work", "service_b")
            await asyncio.sleep(0.01)  # Simulate work
            self.logger.success("ServiceB completed work", "service_b")
            return "work_done"
    
    # Create services with logger injection
    service_a = ServiceA(logger)
    service_b = ServiceB(logger)
    
    # Register services
    registry.register("service_a", service_a)
    registry.register("service_b", service_b)
    
    # Execute work across services
    await service_a.do_work()
    await service_b.do_work()
    
    # Verify logging captured across services
    logs = logger.execution_logs
    assert len(logs) == 4  # 2 info + 2 success messages
    
    # Verify logs contain correct execution ID (stored in logger)
    assert logger.current_execution_id == execution_id
    
    # Verify logs from both services using LogEntry attributes
    service_a_logs = [log for log in logs if log.step_name == "service_a"]
    service_b_logs = [log for log in logs if log.step_name == "service_b"]
    
    assert len(service_a_logs) == 2
    assert len(service_b_logs) == 2


@pytest.mark.asyncio
async def test_service_registry_error_handling():
    """Test service registry error handling"""
    registry = ServiceRegistry()
    
    # Test getting non-existent service
    non_existent = registry.get("non_existent_service")
    assert non_existent is None
    
    # Test has() with non-existent service
    assert registry.has("non_existent_service") is False
    
    # Test registering None service
    registry.register("null_service", None)
    assert registry.has("null_service") is True
    assert registry.get("null_service") is None


@pytest.mark.asyncio
async def test_service_registry_with_real_pipeline():
    """Test service registry integration with pipeline components"""
    from ia_modules.pipeline.core import Step
    
    registry = ServiceRegistry()
    logger = registry.get("central_logger")
    
    class IntegrationStep(Step):
        def __init__(self, name: str, config: dict, services: ServiceRegistry):
            super().__init__(name, config)
            self.services = services
            self.logger = services.get("central_logger")

        async def run(self, data: dict) -> dict:
            self.logger.info(f"Starting {self.name}", self.name)

            # Simulate getting another service
            if self.services.has("data_validator"):
                self.services.get("data_validator")
                # Use validator if available

            result = {"step": self.name, "processed": True, "input": data}
            self.logger.success(f"Completed {self.name}", self.name)
            return result
    
    # Register a data validator service
    class DataValidator:
        def validate(self, data):
            return True
    
    registry.register("data_validator", DataValidator())
    
    # Create step with services
    step = IntegrationStep("integration_step", {}, registry)
    
    # Execute step
    logger.set_execution_id("service_integration_test")
    result = await step.run({"test": "data"})
    
    assert result["processed"] is True
    assert result["step"] == "integration_step"
    
    # Verify logging occurred
    logs = logger.execution_logs
    assert len(logs) >= 2  # Start and success messages
    
    step_logs = [log for log in logs if log.step_name == "integration_step"]
    assert len(step_logs) >= 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])