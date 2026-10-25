"""Service Container - Dependency Injection Container for Showcase App"""

from typing import TYPE_CHECKING, Optional
from nexusql import DatabaseManager
from ia_modules.agents.subprocess_executor import SubprocessExecutor
from services.metrics_service import MetricsService
from services.pipeline_service import PipelineService
from services.reliability_service import ReliabilityService
from services.scheduler_service import SchedulerService
from services.plugin_service import PluginService
from services.guardrails_service import GuardrailsService
from services.agent_execution_service import AgentExecutionService

if TYPE_CHECKING:
    from api.websocket import ConnectionManager
    from services.collaboration_service import CollaborationService
    from services.pattern_service import PatternService


class ServiceContainer:
    """Container holding all application services"""

    def __init__(self):
        self.db_manager: Optional[DatabaseManager] = None
        self.agent_executor: Optional[SubprocessExecutor] = None
        self.metrics_service: Optional[MetricsService] = None
        self.pipeline_service: Optional[PipelineService] = None
        self.reliability_service: Optional[ReliabilityService] = None
        self.scheduler_service: Optional[SchedulerService] = None
        self.plugin_service: Optional[PluginService] = None
        self.guardrails_service: Optional[GuardrailsService] = None
        self.agent_execution_service: Optional[AgentExecutionService] = None
        # WebSocket manager — single process-wide broadcaster
        self.ws_manager: Optional["ConnectionManager"] = None
        # Services that take the whole container so they can resolve their own
        # deps (reliability, ws, executor, …) without every caller re-assembling
        # the list. Constructed at startup in main.py lifespan.
        self.collaboration_service: Optional["CollaborationService"] = None
        self.pattern_service: Optional["PatternService"] = None
