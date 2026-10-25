"""
Tests for pipeline.pipeline_models module
"""

import pytest
from datetime import datetime
from pydantic import ValidationError

from ia_modules.pipeline.pipeline_models import (
    PipelineConfiguration,
    PipelineConfigurationCreate,
    PipelineConfigurationSummary,
    PipelineExecution,
    PipelineExecutionCreate,
    PipelineExecutionSummary,
    PipelineExecutionUpdate,
    PipelineExecutionRequest,
    PipelineExecutionResponse,
    row_to_configuration,
    row_to_configuration_summary,
    row_to_execution,
    row_to_execution_summary
)


class TestPipelineConfiguration:
    """Test PipelineConfiguration model"""

    def test_pipeline_configuration_basic(self):
        """Test basic PipelineConfiguration creation"""
        now = datetime.now()
        config = PipelineConfiguration(
            uuid="test-uuid",
            name="Test Pipeline",
            description="A test pipeline",
            pipeline_json={"steps": []},
            user_id=1,
            created_at=now,
            updated_at=now
        )

        assert config.uuid == "test-uuid"
        assert config.name == "Test Pipeline"
        assert config.description == "A test pipeline"
        assert config.pipeline_json == {"steps": []}
        assert config.user_id == 1
        assert config.created_at == now
        assert config.updated_at == now

    def test_pipeline_configuration_no_description(self):
        """Test PipelineConfiguration without description"""
        now = datetime.now()
        config = PipelineConfiguration(
            uuid="test-uuid",
            name="Test Pipeline",
            pipeline_json={"steps": []},
            user_id=1,
            created_at=now,
            updated_at=now
        )

        assert config.description is None

    def test_pipeline_json_string_parsing(self):
        """Test that pipeline_json string is parsed"""
        now = datetime.now()
        json_str = '{"steps": [{"name": "step1"}]}'
        config = PipelineConfiguration(
            uuid="test-uuid",
            name="Test Pipeline",
            pipeline_json=json_str,
            user_id=1,
            created_at=now,
            updated_at=now
        )

        assert isinstance(config.pipeline_json, dict)
        assert config.pipeline_json == {"steps": [{"name": "step1"}]}

    def test_datetime_string_parsing(self):
        """Test that datetime strings are parsed"""
        config = PipelineConfiguration(
            uuid="test-uuid",
            name="Test Pipeline",
            pipeline_json={"steps": []},
            user_id=1,
            created_at="2025-01-01T12:00:00",
            updated_at="2025-01-01T13:00:00"
        )

        assert isinstance(config.created_at, datetime)
        assert isinstance(config.updated_at, datetime)

    def test_datetime_iso_with_z(self):
        """Test datetime parsing with Z suffix"""
        config = PipelineConfiguration(
            uuid="test-uuid",
            name="Test Pipeline",
            pipeline_json={"steps": []},
            user_id=1,
            created_at="2025-01-01T12:00:00Z",
            updated_at="2025-01-01T13:00:00Z"
        )

        assert isinstance(config.created_at, datetime)
        assert isinstance(config.updated_at, datetime)


class TestPipelineConfigurationCreate:
    """Test PipelineConfigurationCreate model"""

    def test_configuration_create_basic(self):
        """Test basic PipelineConfigurationCreate"""
        create = PipelineConfigurationCreate(
            name="New Pipeline",
            description="New pipeline description",
            pipeline_json={"steps": []}
        )

        assert create.name == "New Pipeline"
        assert create.description == "New pipeline description"
        assert create.pipeline_json == {"steps": []}

    def test_configuration_create_no_description(self):
        """Test PipelineConfigurationCreate without description"""
        create = PipelineConfigurationCreate(
            name="New Pipeline",
            pipeline_json={"steps": []}
        )

        assert create.description is None


class TestPipelineConfigurationSummary:
    """Test PipelineConfigurationSummary model"""

    def test_configuration_summary_basic(self):
        """Test basic PipelineConfigurationSummary"""
        now = datetime.now()
        summary = PipelineConfigurationSummary(
            uuid="test-uuid",
            name="Test Pipeline",
            description="Test description",
            created_at=now,
            updated_at=now
        )

        assert summary.uuid == "test-uuid"
        assert summary.name == "Test Pipeline"
        assert summary.description == "Test description"
        assert summary.created_at == now
        assert summary.updated_at == now

    def test_configuration_summary_datetime_parsing(self):
        """Test datetime parsing in summary"""
        summary = PipelineConfigurationSummary(
            uuid="test-uuid",
            name="Test Pipeline",
            created_at="2025-01-01T12:00:00",
            updated_at="2025-01-01T13:00:00"
        )

        assert isinstance(summary.created_at, datetime)
        assert isinstance(summary.updated_at, datetime)


class TestPipelineExecution:
    """Test PipelineExecution model"""

    def test_pipeline_execution_basic(self):
        """Test basic PipelineExecution creation"""
        now = datetime.now()
        execution = PipelineExecution(
            uuid="exec-uuid",
            configuration_uuid="config-uuid",
            execution_id="exec-123",
            status="running",
            pipeline_name="Test Pipeline",
            user_id=1,
            input_data={"key": "value"},
            output_data={"result": "success"},
            error_message=None,
            started_at=now,
            completed_at=None,
            execution_time_ms=None
        )

        assert execution.uuid == "exec-uuid"
        assert execution.configuration_uuid == "config-uuid"
        assert execution.execution_id == "exec-123"
        assert execution.status == "running"
        assert execution.pipeline_name == "Test Pipeline"
        assert execution.user_id == 1
        assert execution.input_data == {"key": "value"}
        assert execution.output_data == {"result": "success"}
        assert execution.started_at == now

    def test_pipeline_execution_status_validation(self):
        """Test that invalid status is rejected"""
        now = datetime.now()

        with pytest.raises(ValidationError):
            PipelineExecution(
                uuid="exec-uuid",
                execution_id="exec-123",
                status="invalid_status",  # Invalid status
                pipeline_name="Test Pipeline",
                user_id=1,
                started_at=now
            )

    def test_pipeline_execution_valid_statuses(self):
        """Test all valid statuses"""
        now = datetime.now()
        valid_statuses = ["pending", "running", "completed", "failed"]

        for status in valid_statuses:
            execution = PipelineExecution(
                uuid="exec-uuid",
                execution_id="exec-123",
                status=status,
                pipeline_name="Test Pipeline",
                user_id=1,
                started_at=now
            )
            assert execution.status == status

    def test_pipeline_execution_json_data_parsing(self):
        """Test that JSON string data is parsed"""
        now = datetime.now()
        execution = PipelineExecution(
            uuid="exec-uuid",
            execution_id="exec-123",
            status="completed",
            pipeline_name="Test Pipeline",
            user_id=1,
            input_data='{"key": "value"}',
            output_data='{"result": "success"}',
            started_at=now
        )

        assert isinstance(execution.input_data, dict)
        assert isinstance(execution.output_data, dict)
        assert execution.input_data == {"key": "value"}
        assert execution.output_data == {"result": "success"}

    def test_pipeline_execution_datetime_parsing(self):
        """Test datetime parsing in execution"""
        execution = PipelineExecution(
            uuid="exec-uuid",
            execution_id="exec-123",
            status="completed",
            pipeline_name="Test Pipeline",
            user_id=1,
            started_at="2025-01-01T12:00:00",
            completed_at="2025-01-01T12:05:00"
        )

        assert isinstance(execution.started_at, datetime)
        assert isinstance(execution.completed_at, datetime)


class TestPipelineExecutionCreate:
    """Test PipelineExecutionCreate model"""

    def test_execution_create_basic(self):
        """Test basic PipelineExecutionCreate"""
        create = PipelineExecutionCreate(
            execution_id="exec-123",
            configuration_uuid="config-uuid",
            pipeline_name="Test Pipeline",
            user_id=1,
            input_data={"key": "value"}
        )

        assert create.execution_id == "exec-123"
        assert create.configuration_uuid == "config-uuid"
        assert create.pipeline_name == "Test Pipeline"
        assert create.user_id == 1
        assert create.input_data == {"key": "value"}

    def test_execution_create_no_optional_fields(self):
        """Test PipelineExecutionCreate without optional fields"""
        create = PipelineExecutionCreate(
            execution_id="exec-123",
            pipeline_name="Test Pipeline",
            user_id=1
        )

        assert create.configuration_uuid is None
        assert create.input_data is None


class TestPipelineExecutionSummary:
    """Test PipelineExecutionSummary model"""

    def test_execution_summary_basic(self):
        """Test basic PipelineExecutionSummary"""
        now = datetime.now()
        summary = PipelineExecutionSummary(
            uuid="exec-uuid",
            configuration_uuid="config-uuid",
            execution_id="exec-123",
            status="completed",
            pipeline_name="Test Pipeline",
            started_at=now,
            completed_at=now,
            execution_time_ms=5000
        )

        assert summary.uuid == "exec-uuid"
        assert summary.configuration_uuid == "config-uuid"
        assert summary.execution_id == "exec-123"
        assert summary.status == "completed"
        assert summary.pipeline_name == "Test Pipeline"
        assert summary.started_at == now
        assert summary.completed_at == now
        assert summary.execution_time_ms == 5000


class TestPipelineExecutionUpdate:
    """Test PipelineExecutionUpdate model"""

    def test_execution_update_basic(self):
        """Test basic PipelineExecutionUpdate"""
        update = PipelineExecutionUpdate(
            status="completed",
            output_data={"result": "success"},
            error_message=None,
            execution_time_ms=5000
        )

        assert update.status == "completed"
        assert update.output_data == {"result": "success"}
        assert update.error_message is None
        assert update.execution_time_ms == 5000

    def test_execution_update_status_validation(self):
        """Test status validation in update"""
        with pytest.raises(ValidationError):
            PipelineExecutionUpdate(
                status="invalid_status"
            )


class TestPipelineExecutionRequest:
    """Test PipelineExecutionRequest model"""

    def test_execution_request_basic(self):
        """Test basic PipelineExecutionRequest"""
        request = PipelineExecutionRequest(
            pipeline_json={"steps": []},
            input_data={"key": "value"}
        )

        assert request.pipeline_json == {"steps": []}
        assert request.input_data == {"key": "value"}

    def test_execution_request_no_input_data(self):
        """Test PipelineExecutionRequest without input_data"""
        request = PipelineExecutionRequest(
            pipeline_json={"steps": []}
        )

        assert request.input_data is None


class TestPipelineExecutionResponse:
    """Test PipelineExecutionResponse model"""

    def test_execution_response_basic(self):
        """Test basic PipelineExecutionResponse"""
        response = PipelineExecutionResponse(
            execution_id="exec-123",
            status="running",
            message="Pipeline started successfully"
        )

        assert response.execution_id == "exec-123"
        assert response.status == "running"
        assert response.message == "Pipeline started successfully"


class TestRowConversionFunctions:
    """Test row conversion functions"""

    def test_row_to_configuration_dict(self):
        """Test row_to_configuration with dict input"""
        now = datetime.now()
        row = {
            "uuid": "test-uuid",
            "name": "Test Pipeline",
            "description": "Test description",
            "pipeline_json": '{"steps": []}',
            "user_id": 1,
            "created_at": now,
            "updated_at": now
        }

        config = row_to_configuration(row)

        assert isinstance(config, PipelineConfiguration)
        assert config.uuid == "test-uuid"
        assert config.name == "Test Pipeline"
        assert config.description == "Test description"
        assert config.pipeline_json == {"steps": []}
        assert config.user_id == 1

    def test_row_to_configuration_tuple(self):
        """Test row_to_configuration with tuple input"""
        now = datetime.now()
        row = ("test-uuid", "Test Pipeline", "Test description", '{"steps": []}', 1, now, now)

        config = row_to_configuration(row)

        assert isinstance(config, PipelineConfiguration)
        assert config.uuid == "test-uuid"
        assert config.name == "Test Pipeline"
        assert config.description == "Test description"
        assert config.pipeline_json == {"steps": []}

    def test_row_to_configuration_with_dict_pipeline_json(self):
        """Test row_to_configuration when pipeline_json is already a dict"""
        now = datetime.now()
        row = {
            "uuid": "test-uuid",
            "name": "Test Pipeline",
            "description": "Test description",
            "pipeline_json": {"steps": []},  # Already a dict
            "user_id": 1,
            "created_at": now,
            "updated_at": now
        }

        config = row_to_configuration(row)
        assert config.pipeline_json == {"steps": []}

    def test_row_to_configuration_summary_dict(self):
        """Test row_to_configuration_summary with dict input"""
        now = datetime.now()
        row = {
            "uuid": "test-uuid",
            "name": "Test Pipeline",
            "description": "Test description",
            "created_at": now,
            "updated_at": now
        }

        summary = row_to_configuration_summary(row)

        assert isinstance(summary, PipelineConfigurationSummary)
        assert summary.uuid == "test-uuid"
        assert summary.name == "Test Pipeline"
        assert summary.description == "Test description"

    def test_row_to_configuration_summary_tuple(self):
        """Test row_to_configuration_summary with tuple input"""
        now = datetime.now()
        row = ("test-uuid", "Test Pipeline", "Test description", now, now)

        summary = row_to_configuration_summary(row)

        assert isinstance(summary, PipelineConfigurationSummary)
        assert summary.uuid == "test-uuid"
        assert summary.name == "Test Pipeline"

    def test_row_to_execution_dict(self):
        """Test row_to_execution with dict input"""
        now = datetime.now()
        row = {
            "uuid": "exec-uuid",
            "configuration_uuid": "config-uuid",
            "execution_id": "exec-123",
            "status": "completed",
            "pipeline_name": "Test Pipeline",
            "user_id": 1,
            "input_data": '{"key": "value"}',
            "output_data": '{"result": "success"}',
            "error_message": None,
            "started_at": now,
            "completed_at": now,
            "execution_time_ms": 5000
        }

        execution = row_to_execution(row)

        assert isinstance(execution, PipelineExecution)
        assert execution.uuid == "exec-uuid"
        assert execution.configuration_uuid == "config-uuid"
        assert execution.execution_id == "exec-123"
        assert execution.status == "completed"
        assert execution.input_data == {"key": "value"}
        assert execution.output_data == {"result": "success"}

    def test_row_to_execution_tuple_full(self):
        """Test row_to_execution with full tuple input"""
        now = datetime.now()
        row = (
            "exec-uuid",
            "config-uuid",
            "exec-123",
            "completed",
            "Test Pipeline",
            1,
            '{"key": "value"}',
            '{"result": "success"}',
            None,
            now,
            now,
            5000
        )

        execution = row_to_execution(row)

        assert isinstance(execution, PipelineExecution)
        assert execution.uuid == "exec-uuid"
        assert execution.configuration_uuid == "config-uuid"
        assert execution.status == "completed"

    def test_row_to_execution_tuple_short(self):
        """Test row_to_execution with short tuple input"""
        datetime.now()
        row = ("exec-uuid", "config-uuid", "exec-123", "running", "Test Pipeline")

        execution = row_to_execution(row)

        assert isinstance(execution, PipelineExecution)
        assert execution.uuid == "exec-uuid"
        assert execution.status == "running"
        assert execution.input_data is None
        assert execution.output_data is None

    def test_row_to_execution_dict_with_none_data(self):
        """Test row_to_execution with None input/output data"""
        now = datetime.now()
        row = {
            "uuid": "exec-uuid",
            "configuration_uuid": "config-uuid",
            "execution_id": "exec-123",
            "status": "pending",
            "pipeline_name": "Test Pipeline",
            "user_id": 1,
            "input_data": None,
            "output_data": None,
            "error_message": None,
            "started_at": now,
            "completed_at": None,
            "execution_time_ms": None
        }

        execution = row_to_execution(row)

        assert execution.input_data is None
        assert execution.output_data is None

    def test_row_to_execution_invalid_type(self):
        """Test row_to_execution with invalid input type"""
        with pytest.raises(ValueError, match="Unsupported row format"):
            row_to_execution("invalid")

    def test_row_to_execution_summary_dict(self):
        """Test row_to_execution_summary with dict input"""
        now = datetime.now()
        row = {
            "uuid": "exec-uuid",
            "configuration_uuid": "config-uuid",
            "execution_id": "exec-123",
            "status": "completed",
            "pipeline_name": "Test Pipeline",
            "started_at": now,
            "completed_at": now,
            "execution_time_ms": 5000
        }

        summary = row_to_execution_summary(row)

        assert isinstance(summary, PipelineExecutionSummary)
        assert summary.uuid == "exec-uuid"
        assert summary.execution_id == "exec-123"
        assert summary.status == "completed"

    def test_row_to_execution_summary_tuple(self):
        """Test row_to_execution_summary with tuple input"""
        now = datetime.now()
        row = ("exec-uuid", "config-uuid", "exec-123", "completed", "Test Pipeline", now, now, 5000)

        summary = row_to_execution_summary(row)

        assert isinstance(summary, PipelineExecutionSummary)
        assert summary.uuid == "exec-uuid"
        assert summary.status == "completed"
