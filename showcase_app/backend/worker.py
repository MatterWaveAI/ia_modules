"""
Scheduler Worker Process

Runs the scheduler in a separate process to avoid blocking the main server.
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent))

from services.scheduler_service import SchedulerService
from services.pipeline_service import PipelineService
from services.metrics_service import MetricsService
from nexusql import DatabaseManager
from ia_modules.database import MIGRATIONS_DIR

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


async def run_worker():
    """Run the scheduler worker"""
    logger.info("Starting Scheduler Worker...")

    # Initialize database
    db_url = os.getenv('DATABASE_URL', 'sqlite:///./showcase_app.db')
    db_manager = DatabaseManager(db_url)
    await db_manager.initialize(app_migration_paths=[str(MIGRATIONS_DIR)])
    logger.info(f"✓ Database connected ({db_manager.config.database_type.value})")

    # Initialize services
    metrics_service = MetricsService(db_manager)
    pipeline_service = PipelineService(metrics_service, db_manager)
    scheduler_service = SchedulerService(pipeline_service, db_manager)

    logger.info("✓ Scheduler Worker started successfully")
    logger.info("Press Ctrl+C to stop the worker")

    try:
        # Keep the worker running
        while True:
            await asyncio.sleep(1)
    except KeyboardInterrupt:
        logger.info("\nStopping worker...")
    finally:
        # Cleanup
        await scheduler_service.cleanup()
        await metrics_service.cleanup()
        db_manager.disconnect()
        logger.info("Worker stopped")


if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user")
        sys.exit(0)
