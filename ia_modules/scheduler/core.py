"""
Pipeline Scheduler - Schedule pipeline execution with various triggers
"""

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
import logging


class BaseTrigger(ABC):
    """Base class for schedule triggers"""

    @abstractmethod
    def should_run(self, last_run: Optional[datetime] = None) -> bool:
        """Check if pipeline should run now"""
        pass

    @abstractmethod
    def next_run_time(self, last_run: Optional[datetime] = None) -> Optional[datetime]:
        """Calculate next run time"""
        pass


@dataclass
class CronTrigger(BaseTrigger):
    """
    Cron-style schedule trigger.

    Example:
        >>> trigger = CronTrigger("0 9 * * MON-FRI")  # 9am weekdays
        >>> trigger = CronTrigger("0 */6 * * *")  # Every 6 hours
        >>> trigger = CronTrigger("0 0 1 * *")  # First day of month
    """
    cron_expression: str

    def should_run(self, last_run: Optional[datetime] = None) -> bool:
        """Check if should run based on cron schedule"""
        # Simple implementation - full cron parsing would use croniter library
        now = datetime.now()

        if last_run is None:
            return True

        # Parse simple cron expressions
        parts = self.cron_expression.split()
        if len(parts) != 5:
            return False

        minute, hour, day, month, weekday = parts

        # Check if current time matches
        if minute != '*' and now.minute != int(minute):
            return False
        if hour != '*' and now.hour != int(hour):
            return False
        if day != '*' and now.day != int(day):
            return False
        if month != '*' and now.month != int(month):
            return False

        # Simple check - has at least 1 minute passed
        return (now - last_run).total_seconds() >= 60

    def next_run_time(self, last_run: Optional[datetime] = None) -> Optional[datetime]:
        """Calculate next run time (simplified)"""
        now = datetime.now()
        if last_run is None:
            return now

        # Simple implementation - add 1 day
        return now + timedelta(days=1)


@dataclass
class IntervalTrigger(BaseTrigger):
    """
    Interval-based trigger - run every X seconds/minutes/hours.

    Example:
        >>> trigger = IntervalTrigger(minutes=30)  # Every 30 minutes
        >>> trigger = IntervalTrigger(hours=6)  # Every 6 hours
        >>> trigger = IntervalTrigger(seconds=300)  # Every 5 minutes
    """
    seconds: int = 0
    minutes: int = 0
    hours: int = 0
    days: int = 0

    def __post_init__(self):
        self.interval_seconds = (
            self.seconds +
            self.minutes * 60 +
            self.hours * 3600 +
            self.days * 86400
        )

    def should_run(self, last_run: Optional[datetime] = None) -> bool:
        """Check if interval has elapsed"""
        if last_run is None:
            return True

        elapsed = (datetime.now() - last_run).total_seconds()
        return elapsed >= self.interval_seconds

    def next_run_time(self, last_run: Optional[datetime] = None) -> Optional[datetime]:
        """Calculate next run time"""
        if last_run is None:
            return datetime.now()

        return last_run + timedelta(seconds=self.interval_seconds)


@dataclass
class EventTrigger(BaseTrigger):
    """
    Event-based trigger - run when event occurs.

    Example:
        >>> trigger = EventTrigger("file_uploaded")
        >>> trigger = EventTrigger("user_registered")
    """
    event_name: str

    def should_run(self, last_run: Optional[datetime] = None) -> bool:
        """Event triggers are manually fired"""
        return False

    def next_run_time(self, last_run: Optional[datetime] = None) -> Optional[datetime]:
        """Event triggers don't have scheduled time"""
        return None


@dataclass
class ScheduledJob:
    """Represents a scheduled pipeline job"""
    job_id: str
    pipeline_id: str
    trigger: BaseTrigger
    input_data: Dict[str, Any]
    last_run: Optional[datetime] = None
    next_run: Optional[datetime] = None
    enabled: bool = True


class Scheduler:
    """
    Pipeline scheduler.

    Schedules pipeline execution with various triggers.

    Example:
        >>> scheduler = Scheduler()
        >>> scheduler.schedule_pipeline(
        ...     "daily-report",
        ...     pipeline_id="report-pipeline",
        ...     trigger=CronTrigger("0 9 * * MON-FRI"),
        ...     input_data={"report_type": "daily"}
        ... )
        >>> await scheduler.start()
    """

    def __init__(self):
        self.jobs: Dict[str, ScheduledJob] = {}
        self.running = False
        self.logger = logging.getLogger("Scheduler")
        self._task: Optional[asyncio.Task] = None

    def schedule_pipeline(
        self,
        job_id: str,
        pipeline_id: str,
        trigger: BaseTrigger,
        input_data: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        Schedule a pipeline for execution.

        Args:
            job_id: Unique job identifier
            pipeline_id: Pipeline to execute
            trigger: When to run (CronTrigger, IntervalTrigger, EventTrigger)
            input_data: Input data for pipeline

        Example:
            >>> scheduler.schedule_pipeline(
            ...     "hourly-sync",
            ...     pipeline_id="data-sync",
            ...     trigger=IntervalTrigger(hours=1)
            ... )
        """
        job = ScheduledJob(
            job_id=job_id,
            pipeline_id=pipeline_id,
            trigger=trigger,
            input_data=input_data or {},
            next_run=trigger.next_run_time()
        )

        self.jobs[job_id] = job
        self.logger.info(f"Scheduled job: {job_id} for pipeline: {pipeline_id}")

    def unschedule(self, job_id: str) -> bool:
        """
        Remove a scheduled job.

        Args:
            job_id: Job to remove

        Returns:
            True if job was removed, False if not found
        """
        if job_id in self.jobs:
            del self.jobs[job_id]
            self.logger.info(f"Unscheduled job: {job_id}")
            return True
        return False

    def pause_job(self, job_id: str) -> bool:
        """Pause a job (disable without removing)"""
        if job_id in self.jobs:
            self.jobs[job_id].enabled = False
            self.logger.info(f"Paused job: {job_id}")
            return True
        return False

    def resume_job(self, job_id: str) -> bool:
        """Resume a paused job"""
        if job_id in self.jobs:
            self.jobs[job_id].enabled = True
            self.logger.info(f"Resumed job: {job_id}")
            return True
        return False

    async def start(self, check_interval: int = 60) -> None:
        """
        Start the scheduler.

        Args:
            check_interval: How often to check for jobs (seconds)

        Example:
            >>> await scheduler.start()  # Check every 60 seconds
            >>> await scheduler.start(check_interval=30)  # Check every 30 seconds
        """
        if self.running:
            self.logger.warning("Scheduler already running")
            return

        self.running = True
        self.logger.info("Scheduler started")

        try:
            while self.running:
                await self._check_jobs()
                await asyncio.sleep(check_interval)
        except asyncio.CancelledError:
            self.logger.info("Scheduler cancelled")
        finally:
            self.running = False

    async def stop(self) -> None:
        """Stop the scheduler"""
        self.logger.info("Stopping scheduler")
        self.running = False

        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass

    async def _check_jobs(self) -> None:
        """Check and run jobs that are due"""
        now = datetime.now()

        for job_id, job in list(self.jobs.items()):
            if not job.enabled:
                continue

            if job.trigger.should_run(job.last_run):
                self.logger.info(f"Running job: {job_id}")
                await self._run_job(job)
                job.last_run = now
                job.next_run = job.trigger.next_run_time(now)

    async def _run_job(self, job: ScheduledJob) -> None:
        """Execute a job (placeholder - integrate with pipeline runner)"""
        # In real implementation, this would:
        # 1. Load the pipeline
        # 2. Execute it with job.input_data
        # 3. Store results
        # 4. Handle errors

        self.logger.info(f"Executing pipeline: {job.pipeline_id}")
        # Placeholder - actual pipeline execution would go here
        # result = await run_pipeline(job.pipeline_id, job.input_data)

    def fire_event(self, event_name: str, input_data: Optional[Dict[str, Any]] = None) -> int:
        """
        Manually fire an event trigger.

        Args:
            event_name: Event to fire
            input_data: Data to pass to pipeline

        Returns:
            Number of jobs triggered

        Example:
            >>> scheduler.fire_event("user_registered", {"user_id": "123"})
        """
        triggered = 0

        for job in self.jobs.values():
            if isinstance(job.trigger, EventTrigger) and job.trigger.event_name == event_name:
                if job.enabled:
                    # Create task to run job asynchronously
                    if input_data:
                        job.input_data = input_data

                    asyncio.create_task(self._run_job(job))
                    triggered += 1

        self.logger.info(f"Fired event '{event_name}', triggered {triggered} jobs")
        return triggered

    def list_jobs(self) -> List[Dict[str, Any]]:
        """
        List all scheduled jobs.

        Returns:
            List of job information

        Example:
            >>> jobs = scheduler.list_jobs()
            >>> for job in jobs:
            ...     print(f"{job['job_id']}: {job['pipeline_id']}")
        """
        return [
            {
                'job_id': job.job_id,
                'pipeline_id': job.pipeline_id,
                'trigger_type': type(job.trigger).__name__,
                'enabled': job.enabled,
                'last_run': job.last_run.isoformat() if job.last_run else None,
                'next_run': job.next_run.isoformat() if job.next_run else None
            }
            for job in self.jobs.values()
        ]
