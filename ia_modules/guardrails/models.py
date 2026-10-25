"""Core guardrails models."""
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime
from pydantic import BaseModel, Field
from enum import Enum
import uuid


class RailType(str, Enum):
    """Types of guardrails."""
    INPUT = "input"
    OUTPUT = "output"
    DIALOG = "dialog"
    RETRIEVAL = "retrieval"
    EXECUTION = "execution"


class RailAction(str, Enum):
    """Actions a rail can take."""
    ALLOW = "allow"
    BLOCK = "block"
    MODIFY = "modify"
    WARN = "warn"
    REDIRECT = "redirect"


class RailResult(BaseModel):
    """Result of applying a guardrail."""
    rail_id: str
    rail_type: RailType
    action: RailAction

    # Original content
    original_content: Any

    # Modified content (if action == MODIFY)
    modified_content: Optional[Any] = None

    # Metadata
    triggered: bool = False
    reason: Optional[str] = None
    confidence: float = 1.0
    metadata: Dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime = Field(default_factory=datetime.now)


class GuardrailConfig(BaseModel):
    """Configuration for a single guardrail."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    name: str
    type: RailType
    enabled: bool = True

    # Triggering conditions
    conditions: List[Dict[str, Any]] = Field(default_factory=list)

    # Actions to take when triggered
    action: RailAction = RailAction.BLOCK
    fallback_message: Optional[str] = None

    # Priority (higher = executed first)
    priority: int = 0

    # Execution settings
    async_execution: bool = False
    timeout_ms: int = 5000

    # Metadata
    description: str = ""
    tags: List[str] = Field(default_factory=list)


class GuardrailsConfig(BaseModel):
    """Complete guardrails configuration."""
    # LLM configuration
    llm_config: Dict[str, Any] = Field(default_factory=dict)

    # Rails by type
    input_rails: List[GuardrailConfig] = Field(default_factory=list)
    output_rails: List[GuardrailConfig] = Field(default_factory=list)
    dialog_rails: List[GuardrailConfig] = Field(default_factory=list)
    retrieval_rails: List[GuardrailConfig] = Field(default_factory=list)
    execution_rails: List[GuardrailConfig] = Field(default_factory=list)

    # Global settings
    streaming: bool = False
    parallel_execution: bool = True
    fail_fast: bool = False

    # Logging and monitoring
    log_all_interactions: bool = True
    alert_on_blocks: bool = True


class GuardrailViolation(BaseModel):
    """Record of a guardrail violation."""
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    rail_id: str
    rail_name: str
    rail_type: RailType
    action_taken: RailAction

    # Content
    original_content: str
    modified_content: Optional[str] = None

    # Context
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    agent_id: Optional[str] = None

    # Details
    reason: str
    severity: Literal["low", "medium", "high", "critical"] = "medium"

    # Timestamps
    timestamp: datetime = Field(default_factory=datetime.now)

    # Additional metadata
    metadata: Dict[str, Any] = Field(default_factory=dict)
