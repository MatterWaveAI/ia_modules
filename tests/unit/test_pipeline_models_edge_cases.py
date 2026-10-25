"""
Edge case tests for pipeline/pipeline_models.py to reach 100% coverage
"""
from datetime import datetime, timezone
from ia_modules.pipeline.pipeline_models import (
    PipelineConfiguration,
    PipelineConfigurationSummary,
    PipelineExecution,
    PipelineExecutionSummary,
)


class TestPipelineConfigurationEdgeCases:
    """Test edge cases in PipelineConfiguration"""

    def test_serialize_datetime_with_none(self):
        """Test that serialize_datetime is called for datetime fields"""
        # Create instance with datetime
        now = datetime.now(timezone.utc)
        config = PipelineConfiguration(
            uuid="test-uuid",
            name="Test Pipeline",
            pipeline_json={"steps": []},
            user_id=1,
            created_at=now,
            updated_at=now
        )

        # Serialize to dict
        data = config.model_dump()

        # Datetimes should be serialized as ISO format strings
        assert isinstance(data['created_at'], str)
        assert isinstance(data['updated_at'], str)
        assert 'T' in data['created_at']  # ISO format

    def test_parse_datetime_with_string(self):
        """Test parse_datetime with ISO string"""
        # Create with ISO string
        config = PipelineConfiguration(
            uuid="test-uuid",
            name="Test Pipeline",
            pipeline_json={"steps": []},
            user_id=1,
            created_at="2024-01-01T12:00:00+00:00",
            updated_at="2024-01-01T12:00:00+00:00"
        )

        # Should be parsed to datetime objects
        assert isinstance(config.created_at, datetime)
        assert isinstance(config.updated_at, datetime)


class TestPipelineConfigurationSummaryEdgeCases:
    """Test edge cases in PipelineConfigurationSummary"""

    def test_serialize_datetime(self):
        """Test datetime serialization in summary"""
        now = datetime.now(timezone.utc)
        summary = PipelineConfigurationSummary(
            uuid="test-uuid",
            name="Test Pipeline",
            description="Test description",
            created_at=now,
            updated_at=now
        )

        # Serialize
        data = summary.model_dump()

        # Datetimes should be ISO strings
        assert isinstance(data['created_at'], str)
        assert isinstance(data['updated_at'], str)


class TestPipelineExecutionEdgeCases:
    """Test edge cases in PipelineExecution"""

    def test_serialize_datetime_with_none_completed_at(self):
        """Test that serialize_datetime handles None for optional datetime fields"""
        execution = PipelineExecution(
            uuid="exec-uuid",
            execution_id="exec-123",
            status="running",
            pipeline_name="Test Pipeline",
            user_id=1,
            started_at=datetime.now(timezone.utc),
            completed_at=None  # None value
        )

        # Serialize
        data = execution.model_dump()

        # completed_at should be None (not serialized string)
        assert data['completed_at'] is None
        assert isinstance(data['started_at'], str)

    def test_serialize_datetime_with_completed_at(self):
        """Test serialize_datetime when completed_at has a value"""
        now = datetime.now(timezone.utc)
        execution = PipelineExecution(
            uuid="exec-uuid",
            execution_id="exec-123",
            status="completed",
            pipeline_name="Test Pipeline",
            user_id=1,
            started_at=now,
            completed_at=now
        )

        # Serialize
        data = execution.model_dump()

        # Both should be serialized
        assert isinstance(data['started_at'], str)
        assert isinstance(data['completed_at'], str)

    def test_parse_datetime_with_string(self):
        """Test parse_datetime with ISO string"""
        execution = PipelineExecution(
            uuid="exec-uuid",
            execution_id="exec-123",
            status="completed",
            pipeline_name="Test Pipeline",
            user_id=1,
            started_at="2024-01-01T12:00:00+00:00",
            completed_at="2024-01-01T13:00:00+00:00"
        )

        # Should be parsed to datetime
        assert isinstance(execution.started_at, datetime)
        assert isinstance(execution.completed_at, datetime)


class TestPipelineExecutionSummaryEdgeCases:
    """Test edge cases in PipelineExecutionSummary"""

    def test_serialize_datetime_with_none_completed_at(self):
        """Test serializing None completed_at in summary"""
        now = datetime.now(timezone.utc)
        summary = PipelineExecutionSummary(
            uuid="exec-uuid",
            execution_id="exec-123",
            status="pending",
            pipeline_name="Test Pipeline",
            started_at=now,  # Required, not optional
            completed_at=None  # Optional
        )

        # Serialize
        data = summary.model_dump()

        # started_at should be string, completed_at should be None
        assert isinstance(data['started_at'], str)
        assert data['completed_at'] is None

    def test_serialize_datetime_with_values(self):
        """Test serializing actual datetime values"""
        now = datetime.now(timezone.utc)
        summary = PipelineExecutionSummary(
            uuid="exec-uuid",
            execution_id="exec-123",
            status="completed",
            pipeline_name="Test Pipeline",
            user_id=1,
            started_at=now,
            completed_at=now
        )

        # Serialize
        data = summary.model_dump()

        # Should be ISO strings
        assert isinstance(data['started_at'], str)
        assert isinstance(data['completed_at'], str)

    def test_parse_datetime_with_z_suffix(self):
        """Test parse_datetime handles Z suffix (Zulu time)"""
        summary = PipelineExecutionSummary(
            uuid="exec-uuid",
            execution_id="exec-123",
            status="completed",
            pipeline_name="Test Pipeline",
            user_id=1,
            started_at="2024-01-01T12:00:00Z",  # Z suffix
            completed_at="2024-01-01T13:00:00Z"
        )

        # Should be parsed correctly
        assert isinstance(summary.started_at, datetime)
        assert isinstance(summary.completed_at, datetime)

    def test_parse_datetime_with_optional_none(self):
        """Test parse_datetime with None for optional field"""
        now = datetime.now(timezone.utc)
        summary = PipelineExecutionSummary(
            uuid="exec-uuid",
            execution_id="exec-123",
            status="pending",
            pipeline_name="Test Pipeline",
            started_at=now,
            completed_at=None  # None for optional field
        )

        # None should be preserved
        assert summary.started_at is not None
        assert summary.completed_at is None
