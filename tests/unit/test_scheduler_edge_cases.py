"""
Edge case tests for scheduler/core.py to improve coverage
"""
import pytest
import asyncio
from datetime import datetime, timedelta
from ia_modules.scheduler.core import (
    CronTrigger,
    IntervalTrigger,
    ScheduledJob,
    Scheduler,
)


class TestCronTriggerEdgeCases:
    """Test edge cases in CronTrigger"""

    def test_should_run_invalid_cron_expression(self):
        """Test should_run returns False for invalid cron expression"""
        trigger = CronTrigger("invalid")
        last_run = datetime.now() - timedelta(minutes=5)

        result = trigger.should_run(last_run)

        assert result is False

    def test_should_run_with_minute_wildcard(self):
        """Test cron with minute wildcard"""
        now = datetime.now()
        # Expression: every minute, specific hour
        trigger = CronTrigger(f"* {now.hour} * * *")
        last_run = now - timedelta(minutes=2)

        result = trigger.should_run(last_run)

        assert result is True

    def test_should_run_hour_mismatch(self):
        """Test cron returns False when hour doesn't match"""
        now = datetime.now()
        # Expression: specific hour that doesn't match current
        different_hour = (now.hour + 1) % 24
        trigger = CronTrigger(f"* {different_hour} * * *")
        last_run = now - timedelta(minutes=2)

        result = trigger.should_run(last_run)

        assert result is False

    def test_should_run_day_mismatch(self):
        """Test cron returns False when day doesn't match"""
        now = datetime.now()
        # Expression: specific day that doesn't match current
        different_day = (now.day % 28) + 1
        trigger = CronTrigger(f"* * {different_day} * *")
        last_run = now - timedelta(minutes=2)

        result = trigger.should_run(last_run)

        assert result is False

    def test_should_run_month_mismatch(self):
        """Test cron returns False when month doesn't match"""
        now = datetime.now()
        # Expression: specific month that doesn't match current
        different_month = (now.month % 12) + 1
        trigger = CronTrigger(f"* * * {different_month} *")
        last_run = now - timedelta(minutes=2)

        result = trigger.should_run(last_run)

        assert result is False


class TestSchedulerEdgeCases:
    """Test edge cases in Scheduler"""

    @pytest.mark.asyncio
    async def test_start_when_already_running(self, caplog):
        """Test start logs warning when scheduler already running"""
        scheduler = Scheduler()

        scheduler.schedule_pipeline(
            job_id="test_job",
            pipeline_id="test_pipeline",
            trigger=IntervalTrigger(seconds=60),
            input_data={}
        )

        # Start scheduler in background
        task = asyncio.create_task(scheduler.start(check_interval=0.1))
        await asyncio.sleep(0.05)  # Let it start

        # Try to start again
        await scheduler.start()

        # Should log warning
        assert "already running" in caplog.text

        # Cleanup
        await scheduler.stop()
        try:
            await task
        except asyncio.CancelledError:
            pass

    @pytest.mark.asyncio
    async def test_stop_with_no_task(self):
        """Test stop when _task is None"""
        scheduler = Scheduler()

        # Stop without starting
        await scheduler.stop()

        # Should not raise error
        assert scheduler.running is False

    @pytest.mark.asyncio
    async def test_stop_cancels_task(self):
        """Test stop properly cancels the scheduler task"""
        scheduler = Scheduler()

        scheduler.schedule_pipeline(
            job_id="test_job",
            pipeline_id="test_pipeline",
            trigger=IntervalTrigger(seconds=60),
            input_data={}
        )

        # Start scheduler
        task = asyncio.create_task(scheduler.start(check_interval=0.1))
        await asyncio.sleep(0.05)  # Let it start

        # Stop scheduler
        await scheduler.stop()

        # Scheduler should have stopped
        assert scheduler.running is False

        # Wait for task to finish (stop() cancels it)
        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected

        assert task.done()

    @pytest.mark.asyncio
    async def test_start_handles_cancellation(self):
        """Test start loop handles CancelledError gracefully"""
        scheduler = Scheduler()

        scheduler.schedule_pipeline(
            job_id="test_job",
            pipeline_id="test_pipeline",
            trigger=IntervalTrigger(seconds=60),
            input_data={}
        )

        # Start and immediately cancel
        task = asyncio.create_task(scheduler.start(check_interval=0.1))
        await asyncio.sleep(0.05)

        # Cancel the task directly
        task.cancel()

        # Wait for task to complete (will raise CancelledError that gets caught)
        try:
            await task
        except asyncio.CancelledError:
            pass  # Expected when directly cancelling

        # running should be False after cancellation
        assert scheduler.running is False

    @pytest.mark.asyncio
    async def test_check_jobs_skips_disabled_jobs(self):
        """Test that _check_jobs skips disabled jobs"""
        scheduler = Scheduler()

        # Manually add a disabled job
        disabled_job = ScheduledJob(
            job_id="disabled_job",
            pipeline_id="test_pipeline",
            trigger=IntervalTrigger(seconds=0.01),
            input_data={},
            enabled=False  # Disabled
        )
        scheduler.jobs["disabled_job"] = disabled_job

        # Run check_jobs - should skip disabled job
        await scheduler._check_jobs()

        # Job should still not have a last_run since it was disabled
        assert disabled_job.last_run is None

    @pytest.mark.asyncio
    async def test_scheduler_with_multiple_jobs(self):
        """Test scheduler handles multiple jobs"""
        scheduler = Scheduler()

        scheduler.schedule_pipeline(
            job_id="job1",
            pipeline_id="pipeline1",
            trigger=IntervalTrigger(seconds=0.01),
            input_data={}
        )
        scheduler.schedule_pipeline(
            job_id="job2",
            pipeline_id="pipeline2",
            trigger=IntervalTrigger(seconds=0.01),
            input_data={}
        )

        # Verify both jobs are scheduled
        assert len(scheduler.jobs) == 2
        assert "job1" in scheduler.jobs
        assert "job2" in scheduler.jobs
