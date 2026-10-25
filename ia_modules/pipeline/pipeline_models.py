"""
Pydantic models for pipeline configurations and executions
"""

from typing import Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field, field_validator, ConfigDict, field_serializer
import json


class PipelineConfiguration(BaseModel):
    """Pipeline configuration model"""
    model_config = ConfigDict(from_attributes=True)

    uuid: str
    name: str
    description: Optional[str] = None
    pipeline_json: Dict[str, Any]
    user_id: int
    created_at: datetime
    updated_at: datetime

    @field_validator('pipeline_json', mode='before')
    @classmethod
    def parse_pipeline_json(cls, v):
        if isinstance(v, str):
            return json.loads(v)
        return v

    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()


class PipelineConfigurationCreate(BaseModel):
    """Model for creating a new pipeline configuration"""
    name: str
    description: Optional[str] = None
    pipeline_json: Dict[str, Any]


class PipelineConfigurationSummary(BaseModel):
    """Summary model for listing pipeline configurations"""
    model_config = ConfigDict(from_attributes=True)

    uuid: str
    name: str
    description: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    @field_validator('created_at', 'updated_at', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str):
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v

    @field_serializer('created_at', 'updated_at')
    def serialize_datetime(self, value: datetime) -> str:
        return value.isoformat()


class PipelineExecution(BaseModel):
    """Pipeline execution model"""
    model_config = ConfigDict(from_attributes=True)

    uuid: str
    configuration_uuid: Optional[str] = None
    execution_id: str
    status: str = Field(..., pattern="^(pending|running|completed|failed)$")
    pipeline_name: str
    user_id: int
    input_data: Optional[Dict[str, Any]] = None
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    execution_time_ms: Optional[int] = None

    @field_validator('input_data', 'output_data', mode='before')
    @classmethod
    def parse_json_data(cls, v):
        if isinstance(v, str) and v:
            return json.loads(v)
        return v

    @field_validator('started_at', 'completed_at', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str) and v:
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v

    @field_serializer('started_at', 'completed_at')
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None


class PipelineExecutionCreate(BaseModel):
    """Model for creating a new pipeline execution"""
    execution_id: str
    configuration_uuid: Optional[str] = None
    pipeline_name: str
    user_id: int
    input_data: Optional[Dict[str, Any]] = None


class PipelineExecutionSummary(BaseModel):
    """Summary model for listing pipeline executions"""
    model_config = ConfigDict(from_attributes=True)

    uuid: str
    configuration_uuid: Optional[str] = None
    execution_id: str
    status: str
    pipeline_name: str
    started_at: datetime
    completed_at: Optional[datetime] = None
    execution_time_ms: Optional[int] = None

    @field_validator('started_at', 'completed_at', mode='before')
    @classmethod
    def parse_datetime(cls, v):
        if isinstance(v, str) and v:
            return datetime.fromisoformat(v.replace('Z', '+00:00'))
        return v

    @field_serializer('started_at', 'completed_at')
    def serialize_datetime(self, value: Optional[datetime]) -> Optional[str]:
        return value.isoformat() if value else None


class PipelineExecutionUpdate(BaseModel):
    """Model for updating pipeline execution status"""
    status: str = Field(..., pattern="^(pending|running|completed|failed)$")
    output_data: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    execution_time_ms: Optional[int] = None


# Request/Response models for API endpoints
class PipelineExecutionRequest(BaseModel):
    """Request model for executing a pipeline"""
    pipeline_json: Dict[str, Any]
    input_data: Optional[Dict[str, Any]] = None


class PipelineExecutionResponse(BaseModel):
    """Response model for pipeline execution"""
    execution_id: str
    status: str
    message: str


def row_to_configuration(row) -> PipelineConfiguration:
    """Convert database row to PipelineConfiguration model"""
    if isinstance(row, (list, tuple)):
        # Handle tuple/list format (index-based)
        return PipelineConfiguration(
            uuid=row[0],
            name=row[1],
            description=row[2],
            pipeline_json=json.loads(row[3]) if isinstance(row[3], str) else row[3],
            user_id=row[4],
            created_at=row[5],
            updated_at=row[6]
        )
    else:
        # Handle dictionary format (key-based)
        return PipelineConfiguration(
            uuid=row["uuid"],
            name=row["name"],
            description=row["description"],
            pipeline_json=json.loads(row["pipeline_json"]) if isinstance(row["pipeline_json"], str) else row["pipeline_json"],
            user_id=row["user_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )


def row_to_configuration_summary(row) -> PipelineConfigurationSummary:
    """Convert database row to PipelineConfigurationSummary model"""
    if isinstance(row, (list, tuple)):
        # Handle tuple/list format (index-based)
        return PipelineConfigurationSummary(
            uuid=row[0],
            name=row[1],
            description=row[2],
            created_at=row[3],
            updated_at=row[4]
        )
    else:
        # Handle dictionary format (key-based)
        return PipelineConfigurationSummary(
            uuid=row["uuid"],
            name=row["name"],
            description=row["description"],
            created_at=row["created_at"],
            updated_at=row["updated_at"]
        )


def row_to_execution(row) -> PipelineExecution:
    """Convert database row to PipelineExecution model"""
    if isinstance(row, dict):
        # Handle dictionary format (key-based) - this is what the real database returns
        return PipelineExecution(
            uuid=row["uuid"],
            configuration_uuid=row.get("configuration_uuid"),
            execution_id=row["execution_id"],
            status=row["status"],
            pipeline_name=row["pipeline_name"],
            user_id=row.get("user_id", 0),
            input_data=json.loads(row["input_data"]) if row.get("input_data") else None,
            output_data=json.loads(row["output_data"]) if row.get("output_data") else None,
            error_message=row.get("error_message"),
            started_at=row["started_at"],
            completed_at=row.get("completed_at"),
            execution_time_ms=row.get("execution_time_ms")
        )
    elif isinstance(row, (list, tuple)):
        # Handle tuple/list format (index-based)
        # Check if we have enough elements for a full execution record
        if len(row) >= 12:  # Full execution with all fields
            return PipelineExecution(
                uuid=row[0],
                configuration_uuid=row[1],
                execution_id=row[2],
                status=row[3],
                pipeline_name=row[4],
                user_id=row[5],
                input_data=json.loads(row[6]) if row[6] else None,
                output_data=json.loads(row[7]) if row[7] else None,
                error_message=row[8],
                started_at=row[9],
                completed_at=row[10],
                execution_time_ms=row[11]
            )
        else:
            # Handle shorter row format - fill in defaults
            return PipelineExecution(
                uuid=row[0] if len(row) > 0 else "",
                configuration_uuid=row[1] if len(row) > 1 else None,
                execution_id=row[2] if len(row) > 2 else "",
                status=row[3] if len(row) > 3 else "pending",
                pipeline_name=row[4] if len(row) > 4 else "",
                user_id=row[5] if len(row) > 5 else 0,
                input_data=json.loads(row[6]) if len(row) > 6 and row[6] else None,
                output_data=json.loads(row[7]) if len(row) > 7 and row[7] else None,
                error_message=row[8] if len(row) > 8 else None,
                started_at=row[9] if len(row) > 9 else datetime.now(),
                completed_at=row[10] if len(row) > 10 else None,
                execution_time_ms=row[11] if len(row) > 11 else None
            )
    else:
        raise ValueError(f"Unsupported row format: {type(row)}")


def row_to_execution_summary(row) -> PipelineExecutionSummary:
    """Convert database row to PipelineExecutionSummary model"""
    if isinstance(row, (list, tuple)):
        # Handle tuple/list format (index-based)
        return PipelineExecutionSummary(
            uuid=row[0],
            configuration_uuid=row[1],
            execution_id=row[2],
            status=row[3],
            pipeline_name=row[4],
            started_at=row[5],
            completed_at=row[6],
            execution_time_ms=row[7]
        )
    else:
        # Handle dictionary format (key-based)
        return PipelineExecutionSummary(
            uuid=row["uuid"],
            configuration_uuid=row.get("configuration_uuid"),
            execution_id=row["execution_id"],
            status=row["status"],
            pipeline_name=row["pipeline_name"],
            started_at=row["started_at"],
            completed_at=row.get("completed_at"),
            execution_time_ms=row.get("execution_time_ms")
        )