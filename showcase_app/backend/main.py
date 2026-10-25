"""
IA Modules Showcase App - FastAPI Backend
Main application entry point
"""
import logging
import os
import sys
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from nexusql import DatabaseManager
from ia_modules.database import MIGRATIONS_DIR

from ia_modules.agents.subprocess_executor import SubprocessExecutor
# DEPRECATED: decision trail feature disabled in showcase. The ia_modules
# DecisionTrailBuilder requires live StateManager/ToolRegistry instances from
# the run being inspected, which the showcase's per-run execution flows don't
# retain. Re-enable only with a proper per-run registry.
# from ia_modules.reliability.decision_trail import DecisionTrailBuilder
from ia_modules.pipeline.importer import PipelineImportService
from ia_modules.telemetry.integration import configure_agent_telemetry, configure_llm_telemetry

# Load environment variables from .env file
load_dotenv()

# Ensure backend directory is in sys.path for services.* imports
_backend_dir = Path(__file__).parent
if str(_backend_dir) not in sys.path:
    sys.path.insert(0, str(_backend_dir))

from api.pipelines import router as pipelines_router  # noqa: E402
from api.execution import router as execution_router  # noqa: E402
from api.metrics import router as metrics_router  # noqa: E402
from api.websocket import router as websocket_router  # noqa: E402
from api.checkpoints import router as checkpoints_router  # noqa: E402
from api.reliability import router as reliability_router  # noqa: E402
from api.scheduler import router as scheduler_router  # noqa: E402
from api.telemetry import router as telemetry_router  # noqa: E402
from api.memory import router as memory_router  # noqa: E402
from api.multi_agent import router as multi_agent_router  # noqa: E402
from api.agents_api import router as agents_router  # noqa: E402
from api.advanced_tools_api import router as advanced_tools_router  # noqa: E402
from api.step_modules import router as step_modules_router  # noqa: E402
from api.hitl import router as hitl_router  # noqa: E402
from api.plugins import router as plugins_router  # noqa: E402
from api.guardrails import router as guardrails_router  # noqa: E402
from api.patterns import router as patterns_router  # noqa: E402
from api.collaboration import router as collaboration_router  # noqa: E402
from services.container import ServiceContainer  # noqa: E402
from services.metrics_service import MetricsService  # noqa: E402
from services.pipeline_service import PipelineService  # noqa: E402
from services.reliability_service import ReliabilityService  # noqa: E402
from services.scheduler_service import SchedulerService  # noqa: E402
from services.telemetry_service import TelemetryService  # noqa: E402
from services.checkpoint_service import CheckpointService  # noqa: E402
from services.memory_service import MemoryService  # noqa: E402
from services.replay_service import ReplayService  # noqa: E402
# DEPRECATED: see note above DecisionTrailBuilder import.
# from services.decision_trail_service import DecisionTrailService
from services.plugin_service import PluginService  # noqa: E402
from services.guardrails_service import GuardrailsService  # noqa: E402
from services.agent_execution_service import AgentExecutionService  # noqa: E402
from services.collaboration_service import CollaborationService  # noqa: E402
from services.pattern_service import PatternService  # noqa: E402
from services.llm_config import get_agent_config  # noqa: E402
from ia_modules.agents.subprocess_executor import set_shared_executor as set_shared_agent_executor  # noqa: E402

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager"""
    # Startup
    logger.info("Starting IA Modules Showcase App...")

    # Initialize service container
    services = ServiceContainer()

    # Initialize database with migrations
    db_url = os.getenv('DATABASE_URL', 'postgresql://localhost/showcase_app')
    services.db_manager = DatabaseManager(db_url)

    # Use built-in migration system - no app-specific migrations needed
    if not await services.db_manager.initialize(apply_schema=True, app_migration_paths=[str(MIGRATIONS_DIR)]):
        raise RuntimeError(f"Database initialization failed. Check DATABASE_URL in .env: {db_url}")
    logger.info(f"✓ Database initialized ({services.db_manager.config.database_type.value})")

    # Shared SubprocessExecutor — one per process. Its Semaphore is the
    # single gate that caps in-flight agent subprocesses across every
    # pipeline run, every collaboration pattern, and every llm_call().
    # Default of 3 keeps memory bounded on a dev box; override with
    # AGENT_MAX_CONCURRENT for larger hosts or CI.
    agent_max_concurrent = int(os.getenv("AGENT_MAX_CONCURRENT", "3"))
    services.agent_executor = SubprocessExecutor(max_concurrent=agent_max_concurrent)
    set_shared_agent_executor(services.agent_executor)
    logger.info(f"✓ Shared agent executor initialized (max_concurrent={agent_max_concurrent})")

    # Initialize services
    services.metrics_service = MetricsService(services.db_manager)
    services.pipeline_service = PipelineService(
        services.metrics_service,
        services.db_manager,
        agent_executor=services.agent_executor,
    )
    services.reliability_service = ReliabilityService(services.db_manager)
    services.scheduler_service = SchedulerService(services.pipeline_service, services.db_manager)
    # Don't call start() - it blocks the event loop
    # await services.scheduler_service.start()
    
    # Initialize telemetry service with tracer from pipeline_service
    agent_telemetry = configure_agent_telemetry(
        collector=services.pipeline_service.telemetry.collector if services.pipeline_service.telemetry else None,
        tracer=services.pipeline_service.tracer
    )
    llm_telemetry = configure_llm_telemetry(
        collector=services.pipeline_service.telemetry.collector if services.pipeline_service.telemetry else None,
        tracer=services.pipeline_service.tracer
    )
    services.telemetry_service = TelemetryService(
        telemetry=services.pipeline_service.telemetry,
        tracer=services.pipeline_service.tracer,
        agent_telemetry=agent_telemetry,
        llm_telemetry=llm_telemetry
    )
    
    # Initialize checkpoint service with checkpointer from pipeline_service
    services.checkpoint_service = CheckpointService(
        checkpointer=services.pipeline_service.checkpointer,
        pipeline_service=services.pipeline_service
    )
    
    # Initialize memory service (memory backend can be added later if needed)
    services.memory_service = MemoryService(memory_backend=None)
    
    # Initialize replay service
    services.replay_service = ReplayService(
        reliability_metrics=services.reliability_service,
        pipeline_service=services.pipeline_service
    )
    
    # DEPRECATED: decision trail wiring disabled. See import note above.
    # decision_trail_builder = DecisionTrailBuilder(
    #     state_manager=...,  # must be the live per-run StateManager
    #     tool_registry=...,  # must be the live per-run ToolRegistry
    #     checkpointer=services.pipeline_service.checkpointer,
    # )
    # services.decision_trail_service = DecisionTrailService(
    #     decision_trail_builder=decision_trail_builder,
    #     reliability_metrics=services.reliability_service,
    # )

    # Initialize plugin service
    services.plugin_service = PluginService()
    logger.info(f"✓ Plugin service initialized with {len(services.plugin_service.list_plugins())} plugins")

    # Initialize guardrails service
    services.guardrails_service = GuardrailsService()
    logger.info("✓ Guardrails service initialized")

    # Initialize agent execution service
    agent_cfg = get_agent_config()
    services.agent_execution_service = AgentExecutionService(
        services.db_manager, agent_cfg["logs_dir"]
    )
    await services.agent_execution_service.initialize()
    backfill = await services.agent_execution_service.scan_and_backfill()
    logger.info("✓ Agent execution service initialized (backfill: %s)", backfill)

    # WebSocket manager — process-wide singleton, exposed on container so
    # services can broadcast without importing api.websocket themselves.
    from api.websocket import get_ws_manager
    services.ws_manager = get_ws_manager()

    # Container-DI services — take the full container in their constructor
    # and resolve their own deps. No lazy init, no per-route boilerplate.
    services.collaboration_service = CollaborationService(services)
    services.pattern_service = PatternService(services)
    logger.info("✓ Collaboration & pattern services initialized")

    logger.info("✓ Services initialized successfully")

    # Import test pipelines on startup
    tests_dir = Path(__file__).parent.parent.parent / "tests" / "pipelines"
    importer = PipelineImportService(services.db_manager, str(tests_dir))
    import_results = await importer.import_all_pipelines()
    logger.info(f"✓ Pipeline import: {import_results['imported']} imported, {import_results['updated']} updated, {import_results['skipped']} skipped")

    # Load imported pipelines into in-memory cache so API can serve them
    await services.pipeline_service.load_pipelines_from_db()

    # Store services on app state
    app.state.services = services

    yield

    # Shutdown
    logger.info("Shutting down services...")
    try:
        if services.scheduler_service:
            await services.scheduler_service.cleanup()
        await services.metrics_service.cleanup()
        if services.db_manager:
            services.db_manager.disconnect()
        logger.info("Shutdown complete")
    except Exception as e:
        logger.error(f"Error during shutdown: {e}")
    finally:
        os._exit(0)


# Create FastAPI app
app = FastAPI(
    title="IA Modules Showcase API",
    description="REST API for IA Modules demonstration app",
    version="0.0.3",
    lifespan=lifespan
)

# Log any 5xx response body so HTTPExceptions raised inside routes
# (which bypass the global exception handler) still show up in server logs.
# The body is drained and re-emitted verbatim so headers, status, media_type,
# and the original response schema (e.g. FastAPI's {"detail": ...}) are
# preserved for clients. Currently no endpoint returns a StreamingResponse;
# if that changes, this middleware will buffer its body into memory on 5xx.
@app.middleware("http")
async def log_5xx_responses(request: Request, call_next):
    response = await call_next(request)
    if response.status_code < 500:
        return response
    body = b"".join([chunk async for chunk in response.body_iterator])
    detail = body.decode("utf-8", errors="replace")
    logger.error(
        f"{response.status_code} on {request.method} {request.url.path}: {detail}"
    )
    return Response(
        content=body,
        status_code=response.status_code,
        headers=dict(response.headers),
        media_type=response.media_type,
    )


# CORS middleware - MUST be added BEFORE routes
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5174",
        "http://127.0.0.1:5174",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["*"],
)


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint"""
    db_type = "unknown"
    services_status = {}
    
    if hasattr(app.state, 'services'):
        services = app.state.services
        if services.db_manager:
            db_type = services.db_manager.config.database_type.value.upper()
            if db_type == "SQLITE":
                db_type = "SQLite"
            elif db_type == "POSTGRESQL":
                db_type = "PostgreSQL"
            elif db_type == "MEMORY":
                db_type = "In-Memory"
        
        services_status = {
            "metrics": services.metrics_service is not None,
            "pipelines": services.pipeline_service is not None,
            "database": services.db_manager is not None,
        }
    
    return {
        "status": "healthy",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "version": "0.0.3",
        "database": db_type,
        "services": services_status
    }


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint with API information"""
    return {
        "name": "IA Modules Showcase API",
        "version": "0.0.3",
        "docs": "/docs",
        "health": "/health",
        "endpoints": {
            "pipelines": "/api/pipelines",
            "execution": "/api/execute",
            "metrics": "/api/metrics",
            "checkpoints": "/api/checkpoints",
            "reliability": "/api/reliability",
            "scheduler": "/api/scheduler",
            "benchmarking": "/api/benchmarking",
            "websocket": "/ws"
        }
    }


# Include routers
app.include_router(pipelines_router, prefix="/api/pipelines", tags=["Pipelines"])
app.include_router(step_modules_router, tags=["Step Modules"])
app.include_router(execution_router, prefix="/api/execute", tags=["Execution"])
app.include_router(metrics_router, prefix="/api/metrics", tags=["Metrics"])
app.include_router(checkpoints_router, prefix="/api/checkpoints", tags=["Checkpoints"])
app.include_router(reliability_router, prefix="/api/reliability", tags=["Reliability"])
app.include_router(scheduler_router, prefix="/api/scheduler", tags=["Scheduler"])
app.include_router(telemetry_router, prefix="/api/telemetry", tags=["Telemetry"])
app.include_router(memory_router, prefix="/api/memory", tags=["Memory"])
app.include_router(multi_agent_router, tags=["Multi-Agent"])
app.include_router(websocket_router, prefix="/ws", tags=["WebSocket"])
app.include_router(hitl_router, prefix="/api/hitl", tags=["Human-in-the-Loop"])

# Advanced AI Features
app.include_router(agents_router, prefix="/api/agents", tags=["Agents"])
app.include_router(advanced_tools_router, prefix="/api/tools", tags=["Advanced Tools"])
app.include_router(plugins_router, prefix="/api/plugins", tags=["Plugins"])
app.include_router(guardrails_router, prefix="/api/guardrails", tags=["Guardrails"])
app.include_router(patterns_router, tags=["Patterns"])
app.include_router(collaboration_router, tags=["Collaboration"])


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle uncaught exceptions"""
    logger.error(
        f"Unhandled exception on {request.method} {request.url.path}: "
        f"{type(exc).__name__}: {exc}",
        exc_info=True,
    )
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "type": type(exc).__name__,
            "detail": str(exc),
            "path": request.url.path,
        }
    )


# Make services accessible to routers
def get_metrics_service() -> MetricsService:
    """Get metrics service instance"""
    return app.state.services.metrics_service


def get_pipeline_service() -> PipelineService:
    """Get pipeline service instance"""
    return app.state.services.pipeline_service


def get_reliability_service() -> ReliabilityService:
    """Get reliability service instance"""
    return app.state.services.reliability_service


def get_scheduler_service() -> SchedulerService:
    """Get scheduler service instance"""
    return app.state.services.scheduler_service


def get_memory_service() -> MemoryService:
    """Get memory service instance"""
    return app.state.services.memory_service


def get_replay_service() -> ReplayService:
    """Get replay service instance"""
    return app.state.services.replay_service


# DEPRECATED: decision trail feature disabled.
# def get_decision_trail_service() -> DecisionTrailService:
#     """Get decision trail service instance"""
#     return app.state.services.decision_trail_service


def get_db_manager() -> DatabaseManager:
    """Get database manager instance"""
    return app.state.services.db_manager


if __name__ == "__main__":
    import uvicorn
    import os

    # On Windows, uvicorn sometimes doesn't handle Ctrl+C well
    # Pass app object directly and use try/except
    try:
        uvicorn.run(
            app,  # Pass app object directly instead of "main:app" string
            host="0.0.0.0",
            port=7331,
            reload=False,
            log_level="info",
            access_log=True
        )
    except KeyboardInterrupt:
        logger.info("\nServer stopped by user")
        os._exit(0)  # Force immediate exit
