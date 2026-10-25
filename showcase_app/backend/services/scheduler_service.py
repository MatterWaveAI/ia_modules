"""Scheduler service using ia_modules library"""

import logging
import uuid
from typing import Dict, Any, Optional, List
from ia_modules.scheduler import Scheduler, CronTrigger, IntervalTrigger

logger = logging.getLogger(__name__)


class SchedulerService:
    """Service for job scheduling using ia_modules"""

    def __init__(self, pipeline_service, db_manager):
        self.pipeline_service = pipeline_service
        self.db_manager = db_manager
        self.jobs = {}

        logger.info("Initializing scheduler service with ia_modules library...")

        # Initialize scheduler (start() will be called asynchronously later)
        self.scheduler = Scheduler()

        logger.info("Scheduler service initialized (not started - will be started asynchronously)")

    async def cleanup(self):
        """Clean up scheduler"""
        if self.scheduler:
            await self.scheduler.stop()

    async def create_job(
        self,
        job_name: str,
        pipeline_id: str,
        cron_expression: Optional[str] = None,
        interval_seconds: Optional[int] = None,
        input_data: Dict[str, Any] = {},
        enabled: bool = True
    ) -> str:
        """Create a scheduled job using library scheduler"""
        try:
            job_id = str(uuid.uuid4())

            # Create trigger based on input
            if cron_expression:
                trigger = CronTrigger(cron_expression)
            elif interval_seconds:
                trigger = IntervalTrigger(interval_seconds)
            else:
                raise ValueError("Either cron_expression or interval_seconds required")

            # Define job function that executes pipeline
            async def job_function():
                logger.info(f"Executing scheduled job {job_id} for pipeline {pipeline_id}")
                await self.pipeline_service.execute_pipeline(
                    pipeline_id=pipeline_id,
                    input_data=input_data
                )

            # Register job with scheduler
            await self.scheduler.schedule_job(
                job_id=job_id,
                trigger=trigger,
                func=job_function,
                enabled=enabled
            )

            # Store job metadata
            self.jobs[job_id] = {
                "job_id": job_id,
                "job_name": job_name,
                "pipeline_id": pipeline_id,
                "cron_expression": cron_expression,
                "interval_seconds": interval_seconds,
                "input_data": input_data,
                "enabled": enabled,
                "executions": []
            }

            logger.info(f"Created scheduled job {job_id}: {job_name}")
            return job_id

        except Exception as e:
            logger.error(f"Failed to create job: {e}")
            raise

    async def list_jobs(
        self,
        pipeline_id: Optional[str] = None,
        enabled_only: bool = False
    ) -> List[Dict[str, Any]]:
        """List all scheduled jobs"""
        jobs = list(self.jobs.values())

        if pipeline_id:
            jobs = [j for j in jobs if j["pipeline_id"] == pipeline_id]

        if enabled_only:
            jobs = [j for j in jobs if j["enabled"]]

        return jobs

    async def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        """Get job details"""
        return self.jobs.get(job_id)

    async def update_job(
        self,
        job_id: str,
        job_name: Optional[str] = None,
        cron_expression: Optional[str] = None,
        interval_seconds: Optional[int] = None,
        input_data: Optional[Dict[str, Any]] = None,
        enabled: Optional[bool] = None
    ) -> bool:
        """Update a scheduled job"""
        if job_id not in self.jobs:
            return False

        job = self.jobs[job_id]

        # Update job metadata
        if job_name is not None:
            job["job_name"] = job_name
        if cron_expression is not None:
            job["cron_expression"] = cron_expression
        if interval_seconds is not None:
            job["interval_seconds"] = interval_seconds
        if input_data is not None:
            job["input_data"] = input_data
        if enabled is not None:
            job["enabled"] = enabled

            # Enable/disable in scheduler
            if enabled:
                await self.scheduler.enable_job(job_id)
            else:
                await self.scheduler.disable_job(job_id)

        return True

    async def delete_job(self, job_id: str) -> bool:
        """Delete a scheduled job"""
        if job_id not in self.jobs:
            return False

        # Remove from scheduler
        await self.scheduler.remove_job(job_id)

        # Remove from local storage
        del self.jobs[job_id]

        logger.info(f"Deleted job {job_id}")
        return True

    async def run_job_now(self, job_id: str) -> str:
        """Manually trigger a job execution"""
        if job_id not in self.jobs:
            raise ValueError(f"Job {job_id} not found")

        job = self.jobs[job_id]

        # Execute pipeline immediately
        execution_id = await self.pipeline_service.execute_pipeline(
            pipeline_id=job["pipeline_id"],
            input_data=job["input_data"]
        )

        # Record execution in job history
        job["executions"].append({
            "execution_id": execution_id,
            "triggered_by": "manual",
            "timestamp": None  # Would be set by scheduler
        })

        return execution_id

    async def get_job_history(self, job_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        """Get job execution history"""
        if job_id not in self.jobs:
            return []

        job = self.jobs[job_id]
        executions = job.get("executions", [])

        return executions[-limit:]
