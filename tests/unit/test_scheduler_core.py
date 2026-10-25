"""
Unit tests for Scheduler system functionality.

Tests the Scheduler class, CronTrigger, IntervalTrigger, and EventTrigger.
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from ia_modules.scheduler.core import (
    Scheduler,
    CronTrigger,
    IntervalTrigger,
    EventTrigger
)


class TestCronTrigger:
    """Test CronTrigger functionality."""

    def test_cron_trigger_creation(self):
        """CronTrigger can be created with cron expression."""
        trigger = CronTrigger("0 9 * * MON-FRI")

        assert trigger.cron_expression == "0 9 * * MON-FRI"

    def test_cron_trigger_next_run_time_no_last_run(self):
        """CronTrigger returns now when no last run."""
        trigger = CronTrigger("0 9 * * *")

        next_run = trigger.next_run_time()

        assert isinstance(next_run, datetime)
        # When no last run, returns current time
        assert abs((next_run - datetime.now()).total_seconds()) < 1

    def test_cron_trigger_next_run_time_with_last_run(self):
        """CronTrigger calculates next run time after last run."""
        trigger = CronTrigger("0 9 * * *")
        last_run = datetime.now() - timedelta(hours=1)

        next_run = trigger.next_run_time(last_run)

        assert isinstance(next_run, datetime)
        assert next_run > datetime.now()

    def test_cron_trigger_should_run_no_last_run(self):
        """CronTrigger should_run returns True when no last run."""
        trigger = CronTrigger("0 9 * * *")

        assert trigger.should_run() is True

    def test_cron_trigger_should_run_wildcard(self):
        """CronTrigger should_run with wildcard matches any time."""
        trigger = CronTrigger("* * * * *")  # Every minute
        last_run = datetime.now() - timedelta(minutes=2)

        # Should return True since more than 1 minute passed
        assert trigger.should_run(last_run) is True


class TestIntervalTrigger:
    """Test IntervalTrigger functionality."""

    def test_interval_trigger_seconds(self):
        """IntervalTrigger can be created with seconds."""
        trigger = IntervalTrigger(seconds=30)

        assert trigger.seconds == 30
        assert trigger.interval_seconds == 30

    def test_interval_trigger_minutes(self):
        """IntervalTrigger can be created with minutes."""
        trigger = IntervalTrigger(minutes=5)

        assert trigger.minutes == 5
        assert trigger.interval_seconds == 300

    def test_interval_trigger_hours(self):
        """IntervalTrigger can be created with hours."""
        trigger = IntervalTrigger(hours=2)

        assert trigger.hours == 2
        assert trigger.interval_seconds == 7200

    def test_interval_trigger_days(self):
        """IntervalTrigger can be created with days."""
        trigger = IntervalTrigger(days=1)

        assert trigger.days == 1
        assert trigger.interval_seconds == 86400

    def test_interval_trigger_combined(self):
        """IntervalTrigger can combine multiple time units."""
        trigger = IntervalTrigger(hours=1, minutes=30, seconds=15)

        assert trigger.hours == 1
        assert trigger.minutes == 30
        assert trigger.seconds == 15
        assert trigger.interval_seconds == 3600 + 1800 + 15

    def test_interval_trigger_next_run_time_no_last_run(self):
        """IntervalTrigger returns now when no last run."""
        trigger = IntervalTrigger(minutes=5)

        next_run = trigger.next_run_time()

        # Should return current time when no last run
        assert isinstance(next_run, datetime)
        assert abs((next_run - datetime.now()).total_seconds()) < 1

    def test_interval_trigger_next_run_after_last(self):
        """IntervalTrigger calculates next run after last run correctly."""
        trigger = IntervalTrigger(hours=1)
        last_run = datetime.now() - timedelta(minutes=30)

        next_run = trigger.next_run_time(last_run)

        # Should be 1 hour after last run
        expected = last_run + timedelta(hours=1)
        diff = abs((next_run - expected).total_seconds())
        assert diff < 1

    def test_interval_trigger_should_run_true(self):
        """IntervalTrigger should_run returns True when interval elapsed."""
        trigger = IntervalTrigger(seconds=1)
        last_run = datetime.now() - timedelta(seconds=2)

        assert trigger.should_run(last_run) is True

    def test_interval_trigger_should_run_false(self):
        """IntervalTrigger should_run returns False when interval not elapsed."""
        trigger = IntervalTrigger(hours=1)
        last_run = datetime.now() - timedelta(minutes=30)

        assert trigger.should_run(last_run) is False

    def test_interval_trigger_should_run_no_last_run(self):
        """IntervalTrigger should_run returns True when no last run."""
        trigger = IntervalTrigger(hours=1)

        assert trigger.should_run() is True


class TestEventTrigger:
    """Test EventTrigger functionality."""

    def test_event_trigger_creation(self):
        """EventTrigger can be created with event name."""
        trigger = EventTrigger("user_registered")

        assert trigger.event_name == "user_registered"

    def test_event_trigger_next_run_time(self):
        """EventTrigger next_run_time returns None."""
        trigger = EventTrigger("data_ready")

        next_run = trigger.next_run_time()

        assert next_run is None

    def test_event_trigger_should_run(self):
        """EventTrigger should_run always returns False (manual fire only)."""
        trigger = EventTrigger("process_complete")

        assert trigger.should_run() is False
        assert trigger.should_run(datetime.now()) is False


@pytest.mark.asyncio
class TestScheduler:
    """Test Scheduler functionality."""

    async def test_scheduler_creation(self):
        """Scheduler can be created."""
        scheduler = Scheduler()

        assert scheduler is not None
        assert len(scheduler.jobs) == 0
        assert scheduler.running is False

    async def test_schedule_pipeline_cron(self):
        """Pipeline can be scheduled with CronTrigger."""
        scheduler = Scheduler()

        scheduler.schedule_pipeline(
            job_id="daily-job",
            pipeline_id="daily-pipeline",
            trigger=CronTrigger("0 9 * * *"),
            input_data={"type": "daily"}
        )

        assert "daily-job" in scheduler.jobs
        job = scheduler.jobs["daily-job"]
        assert job.pipeline_id == "daily-pipeline"
        assert isinstance(job.trigger, CronTrigger)
        assert job.input_data == {"type": "daily"}

    async def test_schedule_pipeline_interval(self):
        """Pipeline can be scheduled with IntervalTrigger."""
        scheduler = Scheduler()

        scheduler.schedule_pipeline(
            job_id="sync-job",
            pipeline_id="sync-pipeline",
            trigger=IntervalTrigger(hours=6),
            input_data={"full_sync": False}
        )

        assert "sync-job" in scheduler.jobs
        job = scheduler.jobs["sync-job"]
        assert job.pipeline_id == "sync-pipeline"
        assert isinstance(job.trigger, IntervalTrigger)

    async def test_schedule_pipeline_event(self):
        """Pipeline can be scheduled with EventTrigger."""
        scheduler = Scheduler()

        scheduler.schedule_pipeline(
            job_id="welcome-job",
            pipeline_id="welcome-pipeline",
            trigger=EventTrigger("user_registered")
        )

        assert "welcome-job" in scheduler.jobs
        job = scheduler.jobs["welcome-job"]
        assert isinstance(job.trigger, EventTrigger)

    async def test_unschedule_job(self):
        """Job can be unscheduled."""
        scheduler = Scheduler()

        scheduler.schedule_pipeline(
            job_id="test-job",
            pipeline_id="test-pipeline",
            trigger=IntervalTrigger(hours=1)
        )

        result = scheduler.unschedule("test-job")

        assert result is True
        assert "test-job" not in scheduler.jobs

    async def test_unschedule_nonexistent_job(self):
        """Unscheduling nonexistent job returns False."""
        scheduler = Scheduler()

        result = scheduler.unschedule("nonexistent-job")

        assert result is False

    async def test_pause_job(self):
        """Job can be paused."""
        scheduler = Scheduler()

        scheduler.schedule_pipeline(
            job_id="test-job",
            pipeline_id="test-pipeline",
            trigger=IntervalTrigger(hours=1)
        )

        result = scheduler.pause_job("test-job")

        assert result is True
        job = scheduler.jobs["test-job"]
        assert job.enabled is False

    async def test_resume_job(self):
        """Job can be resumed."""
        scheduler = Scheduler()

        scheduler.schedule_pipeline(
            job_id="test-job",
            pipeline_id="test-pipeline",
            trigger=IntervalTrigger(hours=1)
        )

        scheduler.pause_job("test-job")
        result = scheduler.resume_job("test-job")

        assert result is True
        job = scheduler.jobs["test-job"]
        assert job.enabled is True

    async def test_pause_nonexistent_job(self):
        """Pausing nonexistent job returns False."""
        scheduler = Scheduler()

        result = scheduler.pause_job("nonexistent-job")

        assert result is False

    async def test_resume_nonexistent_job(self):
        """Resuming nonexistent job returns False."""
        scheduler = Scheduler()

        result = scheduler.resume_job("nonexistent-job")

        assert result is False

    async def test_list_jobs_empty(self):
        """list_jobs returns empty list when no jobs."""
        scheduler = Scheduler()

        jobs = scheduler.list_jobs()

        assert jobs == []

    async def test_list_jobs(self):
        """list_jobs returns all scheduled jobs."""
        scheduler = Scheduler()

        scheduler.schedule_pipeline(
            job_id="job-1",
            pipeline_id="pipeline-1",
            trigger=CronTrigger("0 9 * * *")
        )
        scheduler.schedule_pipeline(
            job_id="job-2",
            pipeline_id="pipeline-2",
            trigger=IntervalTrigger(hours=1)
        )

        jobs = scheduler.list_jobs()

        assert len(jobs) == 2
        job_ids = [job["job_id"] for job in jobs]
        assert "job-1" in job_ids
        assert "job-2" in job_ids

    async def test_list_jobs_includes_trigger_type(self):
        """list_jobs includes trigger type in output."""
        scheduler = Scheduler()

        scheduler.schedule_pipeline(
            job_id="cron-job",
            pipeline_id="pipeline-1",
            trigger=CronTrigger("0 9 * * *")
        )

        jobs = scheduler.list_jobs()

        assert jobs[0]["trigger_type"] == "CronTrigger"

    async def test_fire_event_triggers_job(self):
        """Event can be fired for event-triggered job."""
        scheduler = Scheduler()
        executed = []

        # Override _run_job to track execution
        async def mock_run_job(job):
            executed.append(job.pipeline_id)

        scheduler._run_job = mock_run_job

        scheduler.schedule_pipeline(
            job_id="event-job",
            pipeline_id="event-pipeline",
            trigger=EventTrigger("user_registered")
        )

        # Fire event
        count = scheduler.fire_event("user_registered", {"user_id": "123"})

        # Wait for async task
        await asyncio.sleep(0.1)

        assert count == 1
        assert "event-pipeline" in executed

    async def test_fire_event_no_matching_jobs(self):
        """Firing event with no matching jobs returns 0."""
        scheduler = Scheduler()

        count = scheduler.fire_event("nonexistent_event", {})

        assert count == 0

    async def test_fire_event_paused_job(self):
        """Paused job doesn't execute when event fired."""
        scheduler = Scheduler()
        executed = []

        async def mock_run_job(job):
            executed.append(job.pipeline_id)

        scheduler._run_job = mock_run_job

        scheduler.schedule_pipeline(
            job_id="event-job",
            pipeline_id="event-pipeline",
            trigger=EventTrigger("user_registered")
        )

        scheduler.pause_job("event-job")
        count = scheduler.fire_event("user_registered", {"user_id": "123"})

        await asyncio.sleep(0.1)

        assert count == 0
        assert len(executed) == 0

    async def test_check_jobs_runs_due_job(self):
        """_check_jobs executes jobs that are due."""
        scheduler = Scheduler()
        executed = []

        async def mock_run_job(job):
            executed.append(job.pipeline_id)

        scheduler._run_job = mock_run_job

        scheduler.schedule_pipeline(
            job_id="test-job",
            pipeline_id="test-pipeline",
            trigger=IntervalTrigger(seconds=1),
            input_data={"test": "data"}
        )

        # Set last_run to past so should_run returns True
        scheduler.jobs["test-job"].last_run = datetime.now() - timedelta(seconds=2)

        await scheduler._check_jobs()

        assert len(executed) == 1
        assert executed[0] == "test-pipeline"

    async def test_check_jobs_skips_paused(self):
        """_check_jobs doesn't execute paused jobs."""
        scheduler = Scheduler()
        executed = []

        async def mock_run_job(job):
            executed.append(job.pipeline_id)

        scheduler._run_job = mock_run_job

        scheduler.schedule_pipeline(
            job_id="test-job",
            pipeline_id="test-pipeline",
            trigger=IntervalTrigger(seconds=1)
        )

        scheduler.jobs["test-job"].last_run = datetime.now() - timedelta(seconds=2)
        scheduler.pause_job("test-job")

        await scheduler._check_jobs()

        assert len(executed) == 0

    async def test_start_and_stop_scheduler(self):
        """Scheduler can be started and stopped."""
        scheduler = Scheduler()

        # Start scheduler (non-blocking)
        start_task = asyncio.create_task(scheduler.start(check_interval=1))

        await asyncio.sleep(0.1)
        assert scheduler.running is True

        # Stop scheduler
        await scheduler.stop()

        # Wait for start task to complete
        try:
            await asyncio.wait_for(start_task, timeout=2)
        except asyncio.TimeoutError:
            pass

        assert scheduler.running is False

    async def test_scheduler_updates_last_run(self):
        """Scheduler updates last_run after job execution."""
        scheduler = Scheduler()

        async def mock_run_job(job):
            pass

        scheduler._run_job = mock_run_job

        scheduler.schedule_pipeline(
            job_id="test-job",
            pipeline_id="test-pipeline",
            trigger=IntervalTrigger(hours=1)
        )

        assert scheduler.jobs["test-job"].last_run is None

        scheduler.jobs["test-job"].last_run = datetime.now() - timedelta(hours=2)

        await scheduler._check_jobs()

        # last_run should be updated
        assert scheduler.jobs["test-job"].last_run is not None
        # Should be recent (within last few seconds)
        assert (datetime.now() - scheduler.jobs["test-job"].last_run).total_seconds() < 5
