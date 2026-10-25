"""Pydantic models for API requests and responses"""

from datetime import datetime
from typing import Optional, Dict, List, Any
from pydantic import BaseModel, Field
from enum import Enum


class ExecutionStatus(str, Enum):
    """Pipeline execution status"""
    PENDING = "pending"
    RUNNING = "running"
    PAUSED = "paused"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class PipelineCreate(BaseModel):
    """Create pipeline request"""
    name: str = Field(..., description="Pipeline name")
    description: Optional[str] = Field(None, description="Pipeline description")
    config: Dict[str, Any] = Field(..., description="Pipeline configuration (JSON)")
    tags: List[str] = Field(default_factory=list, description="Pipeline tags")


class PipelineUpdate(BaseModel):
    """Update pipeline request"""
    name: Optional[str] = None
    description: Optional[str] = None
    config: Optional[Dict[str, Any]] = None
    tags: Optional[List[str]] = None


class PipelineResponse(BaseModel):
    """Pipeline response"""
    id: str
    name: str
    description: Optional[str]
    config: Dict[str, Any]
    tags: List[str]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExecutionRequest(BaseModel):
    """Start pipeline execution request"""
    input_data: Dict[str, Any] = Field(default_factory=dict, description="Input data")
    checkpoint_enabled: bool = Field(default=True, description="Enable checkpointing")


class ExecutionResponse(BaseModel):
    """Pipeline execution response"""
    job_id: str
    pipeline_id: str
    status: ExecutionStatus
    input_data: Dict[str, Any]
    output_data: Optional[Dict[str, Any]]
    current_step: Optional[str]
    started_at: datetime
    completed_at: Optional[datetime]
    error: Optional[str]
    progress: float = Field(ge=0, le=1, description="Execution progress (0-1)")

    class Config:
        from_attributes = True


class StepUpdate(BaseModel):
    """Real-time step execution update"""
    job_id: str
    step_id: str
    status: str
    data: Optional[Dict[str, Any]]
    timestamp: datetime


class MetricsReport(BaseModel):
    """Reliability metrics report"""
    svr: float = Field(description="Success Rate")
    cr: float = Field(description="Compensation Rate")
    pc: float = Field(description="Pass Confidence")
    hir: float = Field(description="Human Intervention Rate")
    ma: Optional[float] = Field(None, description="Model Accuracy")
    tcl: Optional[float] = Field(None, description="Tool Call Latency (ms)")
    wct: Optional[float] = Field(None, description="Workflow Completion Time (ms)")
    mtte: Optional[float] = Field(None, description="Mean Time To Error (hours)")
    rsr: Optional[float] = Field(None, description="Retry Success Rate")
    eqs: Optional[float] = Field(None, description="Explanation Quality Score")
    tpw: Optional[float] = Field(None, description="Tokens Per Workflow")
    cpsw: Optional[float] = Field(None, description="Cost Per Successful Workflow")
    total_workflows: int
    total_steps: int
    timestamp: str


class SLOCompliance(BaseModel):
    """SLO compliance status"""
    svr_compliant: bool
    svr_current: Optional[float]
    svr_target: float
    cr_compliant: bool
    cr_current: Optional[float]
    cr_target: float
    hir_compliant: bool
    hir_current: Optional[float]
    hir_target: float
    ma_compliant: bool
    ma_current: Optional[float]
    ma_target: float
    overall_compliant: bool
    timestamp: str


class EventLog(BaseModel):
    """Event log entry"""
    id: str
    event_type: str
    agent_name: str
    success: bool
    timestamp: datetime
    data: Optional[Dict[str, Any]]


class WebSocketMessage(BaseModel):
    """WebSocket message format"""
    type: str  # "step_update", "execution_complete", "metrics_update", etc.
    data: Dict[str, Any]
    timestamp: datetime


# Telemetry Models

class SpanAttributes(BaseModel):
    """Span attributes"""
    job_id: Optional[str] = None
    step_name: Optional[str] = None
    extra: Dict[str, Any] = Field(default_factory=dict)


class SpanResponse(BaseModel):
    """Telemetry span response"""
    span_id: str
    parent_id: Optional[str]
    name: str
    start_time: Optional[str]
    end_time: Optional[str]
    duration_ms: Optional[float]
    status: str = "ok"
    attributes: Dict[str, Any] = Field(default_factory=dict)


class SpanTimelineResponse(BaseModel):
    """Span timeline response"""
    span_id: str
    parent_id: Optional[str]
    name: str
    start_time: Optional[str]
    end_time: Optional[str]
    duration_ms: float = 0
    status: str = "ok"
    depth: int = 0
    attributes: Dict[str, Any] = Field(default_factory=dict)


class TelemetryMetrics(BaseModel):
    """Aggregated telemetry metrics"""
    total_spans: int
    total_duration_ms: float
    step_count: int
    error_count: int
    avg_step_duration_ms: float = 0


# Checkpoint Models

class CheckpointResponse(BaseModel):
    """Checkpoint response"""
    id: str
    job_id: str
    step_name: str
    created_at: Optional[str]
    state_size: int = 0
    metadata: Dict[str, Any] = Field(default_factory=dict)


class CheckpointStateResponse(BaseModel):
    """Checkpoint state response"""
    checkpoint_id: str
    state: Dict[str, Any]


class CheckpointResumeResponse(BaseModel):
    """Checkpoint resume response"""
    original_job_id: str
    new_job_id: str
    resumed_from_checkpoint: str
    resumed_at_step: str


# Memory Models

class MemoryMessage(BaseModel):
    """Memory message"""
    role: str = "user"
    content: str
    timestamp: Optional[str]
    metadata: Dict[str, Any] = Field(default_factory=dict)


class MemoryStats(BaseModel):
    """Memory statistics"""
    message_count: int
    total_tokens: int
    first_message: Optional[str]
    last_message: Optional[str]
    avg_message_length: int = 0


class MemorySearchRequest(BaseModel):
    """Memory search request"""
    query: str = Field(..., min_length=1)
    session_id: Optional[str] = None
    limit: int = Field(10, ge=1, le=100)


# Replay Models

class ReplayExecutionResponse(BaseModel):
    """Replay execution response"""
    original_job_id: str
    replay_job_id: str
    original: Dict[str, Any]
    replay: Dict[str, Any]
    comparison: Dict[str, Any]
    replayed_at: str


class ReplayComparison(BaseModel):
    """Replay comparison"""
    identical: bool
    difference_count: int
    differences: List[Dict[str, Any]]
    output_match: bool
    status_match: bool


class ReplayHistoryItem(BaseModel):
    """Replay history item"""
    replay_id: Optional[str]
    original_job_id: str
    replay_job_id: str
    success: bool
    differences: List[Dict[str, Any]] = Field(default_factory=list)
    replayed_at: Optional[str]


# Step Detail Models

class StepDetailResponse(BaseModel):
    """Detailed step information"""
    step_name: str
    status: str
    started_at: Optional[str]
    completed_at: Optional[str]
    duration_ms: Optional[float]
    input_data: Dict[str, Any] = Field(default_factory=dict)
    output_data: Dict[str, Any] = Field(default_factory=dict)
    error: Optional[str]
    retry_count: int = 0
    tokens: Optional[int]
    cost: Optional[float]
    logs: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# Pipeline Graph Models

class GraphNode(BaseModel):
    """Pipeline graph node"""
    id: str
    type: str = "step"
    label: str
    config: Dict[str, Any] = Field(default_factory=dict)
    position: Dict[str, float] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    """Pipeline graph edge"""
    source: str
    target: str
    condition: Optional[Dict[str, Any]]
    label: Optional[str]


class PipelineGraphResponse(BaseModel):
    """Pipeline graph structure"""
    nodes: List[GraphNode]
    edges: List[GraphEdge]


# Plugin Models

class PluginResponse(BaseModel):
    """Plugin summary response"""
    name: str
    version: str
    author: Optional[str] = None
    description: Optional[str] = None
    type: str
    tags: List[str] = Field(default_factory=list)
    status: str = "loaded"


class PluginDetailResponse(PluginResponse):
    """Plugin detail response with extra fields"""
    config_schema: Optional[Dict[str, Any]] = None
    dependencies: List[str] = Field(default_factory=list)
    dependencies_satisfied: bool = True
    missing_dependencies: List[str] = Field(default_factory=list)


class PluginExecuteRequest(BaseModel):
    """Plugin execution request"""
    params: Dict[str, Any] = Field(default_factory=dict, description="Parameters to pass to the plugin")


class PluginExecuteResponse(BaseModel):
    """Plugin execution response"""
    plugin: str
    type: str
    result: Optional[Any] = None
    error: Optional[str] = None
    success: bool = True


class PluginLoadRequest(BaseModel):
    """Plugin load request"""
    path: str = Field(..., description="File path to load plugin from")


class PluginLoadResponse(BaseModel):
    """Plugin load response"""
    loaded_count: int
    path: str
    success: bool = True
    message: Optional[str] = None


# Guardrails Models

class GuardrailsTestInputRequest(BaseModel):
    """Request to test an input rail"""
    text: str = Field(..., min_length=1, description="Text to test against the rail")
    rail_type: str = Field(..., description="Input rail type: jailbreak, toxicity, or pii")
    options: Optional[Dict[str, Any]] = Field(default=None, description="Rail-specific options")


class GuardrailsTestOutputRequest(BaseModel):
    """Request to test an output rail"""
    text: str = Field(..., min_length=1, description="Text to test against the rail")
    rail_type: str = Field(..., description="Output rail type: toxic_filter, disclaimer, or length_limit")
    options: Optional[Dict[str, Any]] = Field(default=None, description="Rail-specific options")


class GuardrailsPipelineRequest(BaseModel):
    """Request to run a full guardrails pipeline"""
    text: str = Field(..., min_length=1, description="Text to process through the pipeline")
    input_rails: List[str] = Field(default_factory=list, description="Input rails to enable")
    output_rails: List[str] = Field(default_factory=list, description="Output rails to enable")
    options: Dict[str, Any] = Field(default_factory=dict, description="Rail-specific options")


class GuardrailsRailResult(BaseModel):
    """Individual rail execution result"""
    rail_id: str
    rail_type: str
    action: str
    triggered: bool
    confidence: float = 1.0
    reason: Optional[str] = None
    modified_content: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GuardrailsTestResponse(BaseModel):
    """Response from testing a single rail"""
    action: str
    content: Any
    triggered_count: int = 0
    results: List[GuardrailsRailResult] = Field(default_factory=list)
    reason: Optional[str] = None
    blocked_by: Optional[str] = None


class GuardrailsPipelineStepResult(BaseModel):
    """Result of a pipeline step"""
    step: str
    rails_checked: List[str] = Field(default_factory=list)
    action: str
    triggered_count: int = 0
    results: List[GuardrailsRailResult] = Field(default_factory=list)
    blocked: Optional[bool] = None
    reason: Optional[str] = None
    modified_text: Optional[str] = None


class GuardrailsPipelineResponse(BaseModel):
    """Response from running a full guardrails pipeline"""
    original_text: str
    final_text: Optional[str]
    overall_action: str
    blocked: bool
    blocked_at: Optional[str] = None
    steps: List[GuardrailsPipelineStepResult] = Field(default_factory=list)
    engine_stats: Optional[Dict[str, Any]] = None


class GuardrailsRailsListResponse(BaseModel):
    """Response listing all available rails"""
    rails: Dict[str, Any]


# Collaboration Pattern Models

class CollaborationPatternInfo(BaseModel):
    """Collaboration pattern information"""
    id: str
    name: str
    description: str
    use_cases: List[str] = Field(default_factory=list)


class CollaborationHistoryStep(BaseModel):
    """A step in the collaboration history"""
    phase: str
    message: Optional[str] = None
    timestamp: Optional[str] = None


class CollaborationResult(BaseModel):
    """Collaboration execution result"""
    pattern: str
    result: Dict[str, Any] = Field(default_factory=dict)
    history: List[Dict[str, Any]] = Field(default_factory=list)
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
