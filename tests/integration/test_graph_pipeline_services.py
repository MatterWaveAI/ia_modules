"""
Integration tests for GraphPipelineRunner service integrations.

Tests central logger, execution tracker, and service registry integration.
"""

import pytest
from ia_modules.pipeline.graph_pipeline_runner import GraphPipelineRunner
from ia_modules.pipeline.services import ServiceRegistry
from typing import Dict, Any, List
import uuid


class MockCentralLogger:
    """Mock central logger for testing"""

    def __init__(self):
        self.logs: List[Dict[str, Any]] = []
        self.execution_id: str = None

    def set_execution_id(self, execution_id: str):
        self.execution_id = execution_id

    def log(self, level: str, message: str, step_name: str = None, data: Dict[str, Any] = None):
        self.logs.append({
            "level": level,
            "message": message,
            "step_name": step_name,
            "data": data,
            "execution_id": self.execution_id
        })

    async def write_to_database(self, execution_tracker):
        # Simulate writing logs to database
        pass


class MockExecutionTracker:
    """Mock execution tracker for testing"""

    def __init__(self):
        self.executions: Dict[str, Dict[str, Any]] = {}
        self.started: List[str] = []
        self.ended: List[str] = []
        self.step_executions: Dict[str, Dict[str, Any]] = {}

    async def start_execution(self, execution_id: str, pipeline_name: str,
                       pipeline_version: str, input_data: Dict[str, Any] = None):
        self.started.append(execution_id)
        self.executions[execution_id] = {
            "id": execution_id,
            "pipeline_name": pipeline_name,
            "pipeline_version": pipeline_version,
            "input_data": input_data,
            "status": "running"
        }

    async def update_execution_status(self, execution_id: str, status=None, error: str = None, error_message: str = None, **kwargs):
        final_error = error_message if error_message is not None else error
        self.ended.append(execution_id)
        if execution_id in self.executions:
            status_str = status.value if hasattr(status, 'value') else str(status)
            self.executions[execution_id]["status"] = status_str
            self.executions[execution_id]["success"] = status_str == "completed"
            if final_error:
                self.executions[execution_id]["error"] = final_error

    async def get_execution_steps(self, execution_id: str):
        return []

    def end_execution(self, execution_id: str, success: bool, error: str = None):
        self.ended.append(execution_id)
        if execution_id in self.executions:
            self.executions[execution_id]["status"] = "completed" if success else "failed"
            self.executions[execution_id]["success"] = success
            if error:
                self.executions[execution_id]["error"] = error

    async def start_step_execution(self, execution_id: str, step_id: str, step_name: str, step_type: str = None, input_data: Any = None) -> str:
        step_execution_id = f"{execution_id}_{step_id}"
        self.step_executions[step_execution_id] = {
            "execution_id": execution_id,
            "step_id": step_id,
            "step_name": step_name,
            "step_type": step_type,
            "input_data": input_data,
            "status": "running"
        }
        return step_execution_id

    async def complete_step_execution(self, step_execution_id: str, status: str = None, output_data: Any = None, error_message: str = None):
        if step_execution_id in self.step_executions:
            self.step_executions[step_execution_id]["status"] = status or ("completed" if not error_message else "failed")
            self.step_executions[step_execution_id]["output_data"] = output_data
            if error_message:
                self.step_executions[step_execution_id]["error"] = error_message


@pytest.mark.asyncio
class TestGraphPipelineServices:
    """Test service integration in GraphPipelineRunner."""

    async def test_service_registry_integration(self):
        """Runner integrates with ServiceRegistry."""
        services = ServiceRegistry()
        runner = GraphPipelineRunner(services)

        assert runner.services == services

    async def test_central_logger_integration(self):
        """Runner logs to central logger service."""
        services = ServiceRegistry()
        central_logger = MockCentralLogger()
        services.register("central_logger", central_logger)

        runner = GraphPipelineRunner(services)

        config = {
            "name": "Logger Test",
            "version": "1.0.0",
            "steps": [{
                "id": "step1",
                "name": "step1",
                "step_class": "DataTransformStep",
                "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
            }],
            "flow": {"start_at": "step1", "paths": []}
        }

        await runner.run_pipeline_from_json(config, {"value": 5})

        # Verify logger was called
        assert len(central_logger.logs) > 0

        # Check for execution start log
        start_logs = [log for log in central_logger.logs if "Starting pipeline" in log["message"]]
        assert len(start_logs) > 0

        # Check for success log
        success_logs = [log for log in central_logger.logs if log["level"] == "SUCCESS"]
        assert len(success_logs) > 0

    async def test_execution_tracker_integration(self):
        """Runner tracks execution start and end."""
        services = ServiceRegistry()
        execution_tracker = MockExecutionTracker()
        services.register("execution_tracker", execution_tracker)

        runner = GraphPipelineRunner(services)

        config = {
            "name": "Tracker Test",
            "version": "2.0.0",
            "steps": [{
                "id": "step1",
                "name": "step1",
                "step_class": "DataTransformStep",
                "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
            }],
            "flow": {"start_at": "step1", "paths": []}
        }

        await runner.run_pipeline_from_json(config, {"value": 5})

        # Verify execution was tracked
        assert len(execution_tracker.started) == 1
        assert len(execution_tracker.ended) == 1

        execution_id = execution_tracker.started[0]
        assert execution_id in execution_tracker.executions

        execution = execution_tracker.executions[execution_id]
        assert execution["pipeline_name"] == "Tracker Test"
        assert execution["pipeline_version"] == "2.0.0"
        assert execution["status"] == "completed"
        assert execution["success"] is True

    async def test_execution_id_generation(self):
        """Each execution gets unique execution ID."""
        services = ServiceRegistry()
        central_logger = MockCentralLogger()
        services.register("central_logger", central_logger)

        runner = GraphPipelineRunner(services)

        config = {
            "name": "ID Test",
            "steps": [{
                "id": "step1",
                "name": "step1",
                "step_class": "DataTransformStep",
                "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
            }],
            "flow": {"start_at": "step1", "paths": []}
        }

        # Run pipeline twice
        await runner.run_pipeline_from_json(config, {"value": 5})
        first_execution_id = central_logger.execution_id

        await runner.run_pipeline_from_json(config, {"value": 10})
        second_execution_id = central_logger.execution_id

        # Execution IDs should be different
        assert first_execution_id != second_execution_id

        # Both should be valid UUIDs
        uuid.UUID(first_execution_id)
        uuid.UUID(second_execution_id)

    async def test_execution_tracker_on_failure(self):
        """Execution tracker logs failures correctly."""
        services = ServiceRegistry()
        execution_tracker = MockExecutionTracker()
        services.register("execution_tracker", execution_tracker)

        runner = GraphPipelineRunner(services)

        # Invalid config to cause failure
        config = {
            "name": "Failure Test",
            "steps": [{
                "id": "step1",
                "name": "step1",
                "step_class": "NonExistentStep",
                "module": "nonexistent.module"
            }],
            "flow": {"start_at": "step1", "paths": []}
        }

        with pytest.raises(Exception):
            await runner.run_pipeline_from_json(config, {"value": 5})

        # Verify failure was tracked
        assert len(execution_tracker.ended) == 1
        execution_id = execution_tracker.ended[0]

        execution = execution_tracker.executions[execution_id]
        assert execution["success"] is False
        assert "error" in execution

    async def test_logger_logs_step_details(self):
        """Logger captures individual step details."""
        services = ServiceRegistry()
        central_logger = MockCentralLogger()
        services.register("central_logger", central_logger)

        runner = GraphPipelineRunner(services)

        config = {
            "name": "Step Details Test",
            "steps": [
                {
                    "id": "step1",
                    "name": "transform1",
                    "step_class": "DataTransformStep",
                    "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
                },
                {
                    "id": "step2",
                    "name": "transform2",
                    "step_class": "DataTransformStep",
                    "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
                }
            ],
            "flow": {
                "start_at": "step1",
                "paths": [
                    {"from": "step1", "to": "step2", "condition": {"type": "always"}}
                ]
            }
        }

        await runner.run_pipeline_from_json(config, {"value": 5})

        # Check for step configuration logs
        step_logs = [log for log in central_logger.logs if "Step configured" in log["message"]]
        assert len(step_logs) >= 2  # At least 2 steps logged

    async def test_services_optional(self):
        """Runner works without services registered."""
        # No services registered
        services = ServiceRegistry()
        runner = GraphPipelineRunner(services)

        config = {
            "name": "No Services Test",
            "steps": [{
                "id": "step1",
                "name": "step1",
                "step_class": "DataTransformStep",
                "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
            }],
            "flow": {"start_at": "step1", "paths": []}
        }

        # Should work without errors
        result = await runner.run_pipeline_from_json(config, {"value": 5})
        assert result["output"]["value"] == 10

    async def test_combined_services_integration(self):
        """Runner integrates with multiple services simultaneously."""
        services = ServiceRegistry()
        central_logger = MockCentralLogger()
        execution_tracker = MockExecutionTracker()

        services.register("central_logger", central_logger)
        services.register("execution_tracker", execution_tracker)

        runner = GraphPipelineRunner(services)

        config = {
            "name": "Combined Services Test",
            "version": "1.5.0",
            "steps": [{
                "id": "step1",
                "name": "step1",
                "step_class": "DataTransformStep",
                "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
            }],
            "flow": {"start_at": "step1", "paths": []}
        }

        await runner.run_pipeline_from_json(config, {"value": 7})

        # Verify both services were used
        assert len(central_logger.logs) > 0
        assert len(execution_tracker.started) == 1

        # Verify they share the same execution ID
        execution_id = execution_tracker.started[0]
        assert central_logger.execution_id == execution_id

    async def test_execution_stats_populated(self):
        """Execution stats are properly populated."""
        services = ServiceRegistry()
        runner = GraphPipelineRunner(services)

        config = {
            "name": "Stats Test",
            "steps": [{
                "id": "step1",
                "name": "step1",
                "step_class": "DataTransformStep",
                "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
            }],
            "flow": {"start_at": "step1", "paths": []}
        }

        await runner.run_pipeline_from_json(config, {"value": 5})

        # Check stats
        assert "start_time" in runner.execution_stats
        assert "end_time" in runner.execution_stats
        assert runner.execution_stats["start_time"] is not None
        assert runner.execution_stats["end_time"] is not None

        # End time should be after start time
        assert runner.execution_stats["end_time"] >= runner.execution_stats["start_time"]

    async def test_logger_captures_duration(self):
        """Logger captures pipeline execution duration."""
        services = ServiceRegistry()
        central_logger = MockCentralLogger()
        services.register("central_logger", central_logger)

        runner = GraphPipelineRunner(services)

        config = {
            "name": "Duration Test",
            "steps": [{
                "id": "step1",
                "name": "step1",
                "step_class": "DataTransformStep",
                "module": "tests.pipelines.data_flow_pipeline.steps.test_steps"
            }],
            "flow": {"start_at": "step1", "paths": []}
        }

        await runner.run_pipeline_from_json(config, {"value": 5})

        # Look for completion log with duration
        completion_logs = [
            log for log in central_logger.logs
            if "completed in" in log["message"].lower()
        ]
        assert len(completion_logs) > 0

    async def test_custom_service_registration(self):
        """Custom services can be registered and accessed."""
        services = ServiceRegistry()

        # Register custom service
        custom_service = {"name": "custom", "initialized": True}
        services.register("custom_service", custom_service)

        runner = GraphPipelineRunner(services)

        # Service should be accessible
        assert runner.services.get("custom_service") == custom_service


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
