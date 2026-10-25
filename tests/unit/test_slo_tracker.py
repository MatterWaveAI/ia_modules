"""
Unit tests for SLO tracker.

Tests SLOTracker, MTTEMeasurement, RSRMeasurement, and SLOReport.
"""

from datetime import datetime, timedelta, timezone
from ia_modules.reliability.slo_tracker import (
    MTTEMeasurement,
    RSRMeasurement,
    SLOReport,
    SLOTracker
)


class TestMTTEMeasurement:
    """Test MTTEMeasurement dataclass."""

    def test_mtte_measurement_creation(self):
        """MTTEMeasurement can be created."""
        measurement = MTTEMeasurement(
            thread_id="thread-123",
            checkpoint_id="ckpt-456",
            duration_ms=1500,
            timestamp="2025-01-01T00:00:00",
            success=True
        )

        assert measurement.thread_id == "thread-123"
        assert measurement.checkpoint_id == "ckpt-456"
        assert measurement.duration_ms == 1500
        assert measurement.success is True
        assert measurement.error is None

    def test_mtte_measurement_with_error(self):
        """MTTEMeasurement can include error."""
        measurement = MTTEMeasurement(
            thread_id="thread-123",
            checkpoint_id="ckpt-456",
            duration_ms=5000,
            timestamp="2025-01-01T00:00:00",
            success=False,
            error="StateManager not initialized"
        )

        assert measurement.success is False
        assert measurement.error == "StateManager not initialized"


class TestRSRMeasurement:
    """Test RSRMeasurement dataclass."""

    def test_rsr_measurement_creation(self):
        """RSRMeasurement can be created."""
        measurement = RSRMeasurement(
            thread_id="thread-123",
            checkpoint_id="ckpt-456",
            replay_mode="strict",
            success=True,
            timestamp="2025-01-01T00:00:00"
        )

        assert measurement.thread_id == "thread-123"
        assert measurement.replay_mode == "strict"
        assert measurement.success is True

    def test_rsr_measurement_with_error(self):
        """RSRMeasurement can include error."""
        measurement = RSRMeasurement(
            thread_id="thread-123",
            checkpoint_id="ckpt-456",
            replay_mode="strict",
            success=False,
            timestamp="2025-01-01T00:00:00",
            error="Tool not available"
        )

        assert measurement.success is False
        assert measurement.error == "Tool not available"


class TestSLOReport:
    """Test SLOReport dataclass."""

    def test_slo_report_creation(self):
        """SLOReport can be created."""
        report = SLOReport(
            period_start=datetime(2025, 1, 1),
            period_end=datetime(2025, 1, 2),
            mtte_avg_ms=2000,
            mtte_p50_ms=1800,
            mtte_p95_ms=4500,
            mtte_p99_ms=5000,
            rsr=0.98,
            total_mtte_measurements=100,
            total_rsr_attempts=50,
            successful_replays=49
        )

        assert report.mtte_avg_ms == 2000
        assert report.rsr == 0.98

    def test_is_mtte_compliant_pass(self):
        """is_mtte_compliant returns True when under target."""
        report = SLOReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            mtte_avg_ms=2000,
            mtte_p50_ms=1800,
            mtte_p95_ms=250000,  # 4min 10sec - under 5min
            mtte_p99_ms=280000,
            rsr=0.99
        )

        assert report.is_mtte_compliant() is True

    def test_is_mtte_compliant_fail(self):
        """is_mtte_compliant returns False when over target."""
        report = SLOReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            mtte_avg_ms=2000,
            mtte_p50_ms=1800,
            mtte_p95_ms=350000,  # 5min 50sec - over 5min
            mtte_p99_ms=400000,
            rsr=0.99
        )

        assert report.is_mtte_compliant() is False

    def test_is_rsr_compliant_pass(self):
        """is_rsr_compliant returns True when meeting target."""
        report = SLOReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            mtte_avg_ms=2000,
            mtte_p50_ms=1800,
            mtte_p95_ms=250000,
            mtte_p99_ms=280000,
            rsr=0.995  # 99.5% - above 99%
        )

        assert report.is_rsr_compliant() is True

    def test_is_rsr_compliant_fail(self):
        """is_rsr_compliant returns False when below target."""
        report = SLOReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            mtte_avg_ms=2000,
            mtte_p50_ms=1800,
            mtte_p95_ms=250000,
            mtte_p99_ms=280000,
            rsr=0.97  # 97% - below 99%
        )

        assert report.is_rsr_compliant() is False

    def test_is_compliant_all_pass(self):
        """is_compliant returns True when all SLOs met."""
        report = SLOReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            mtte_avg_ms=2000,
            mtte_p50_ms=1800,
            mtte_p95_ms=250000,  # Under 5min
            mtte_p99_ms=280000,
            rsr=0.995  # Above 99%
        )

        assert report.is_compliant() is True

    def test_is_compliant_mtte_fail(self):
        """is_compliant returns False when MTTE fails."""
        report = SLOReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            mtte_avg_ms=2000,
            mtte_p50_ms=1800,
            mtte_p95_ms=350000,  # Over 5min - FAIL
            mtte_p99_ms=400000,
            rsr=0.995
        )

        assert report.is_compliant() is False

    def test_get_violations_none(self):
        """get_violations returns empty when compliant."""
        report = SLOReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            mtte_avg_ms=2000,
            mtte_p50_ms=1800,
            mtte_p95_ms=250000,
            mtte_p99_ms=280000,
            rsr=0.995
        )

        violations = report.get_violations()
        assert len(violations) == 0

    def test_get_violations_both(self):
        """get_violations returns all violations."""
        report = SLOReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            mtte_avg_ms=2000,
            mtte_p50_ms=1800,
            mtte_p95_ms=350000,  # FAIL
            mtte_p99_ms=400000,
            rsr=0.97  # FAIL
        )

        violations = report.get_violations()
        assert len(violations) == 2
        assert any("MTTE" in v for v in violations)
        assert any("RSR" in v for v in violations)


class TestSLOTracker:
    """Test SLOTracker class."""

    async def test_tracker_creation(self):
        """SLOTracker can be created."""
        tracker = SLOTracker()

        assert tracker.mtte_measurements == []
        assert tracker.rsr_measurements == []

    async def test_record_mtte(self):
        """Can record MTTE measurements."""
        tracker = SLOTracker()

        await tracker.record_mtte(
            thread_id="thread-123",
            checkpoint_id="ckpt-456",
            duration_ms=2000,
            success=True
        )

        assert len(tracker.mtte_measurements) == 1
        assert tracker.mtte_measurements[0].duration_ms == 2000
        assert tracker.mtte_measurements[0].success is True

    async def test_record_mtte_failure(self):
        """Can record MTTE failures."""
        tracker = SLOTracker()

        await tracker.record_mtte(
            thread_id="thread-123",
            checkpoint_id="ckpt-456",
            duration_ms=5000,
            success=False,
            error="StateManager error"
        )

        assert len(tracker.mtte_measurements) == 1
        assert tracker.mtte_measurements[0].success is False
        assert tracker.mtte_measurements[0].error == "StateManager error"

    async def test_record_rsr(self):
        """Can record RSR measurements."""
        tracker = SLOTracker()

        await tracker.record_rsr(
            thread_id="thread-123",
            checkpoint_id="ckpt-456",
            replay_mode="strict",
            success=True
        )

        assert len(tracker.rsr_measurements) == 1
        assert tracker.rsr_measurements[0].success is True

    async def test_record_rsr_failure(self):
        """Can record RSR failures."""
        tracker = SLOTracker()

        await tracker.record_rsr(
            thread_id="thread-123",
            checkpoint_id="ckpt-456",
            replay_mode="strict",
            success=False,
            error="Tool unavailable"
        )

        assert len(tracker.rsr_measurements) == 1
        assert tracker.rsr_measurements[0].success is False

    async def test_get_mtte_stats(self):
        """Can calculate MTTE statistics."""
        tracker = SLOTracker()

        # Record various durations
        for duration in [1000, 2000, 3000, 4000, 5000]:
            await tracker.record_mtte(
                thread_id=f"thread-{duration}",
                checkpoint_id="ckpt-1",
                duration_ms=duration,
                success=True
            )

        stats = await tracker.get_mtte_stats()

        assert stats["avg_ms"] == 3000  # (1+2+3+4+5)/5
        assert stats["p50_ms"] == 3000  # Median
        assert stats["count"] == 5

    async def test_get_mtte_stats_excludes_failures(self):
        """MTTE stats exclude failed measurements."""
        tracker = SLOTracker()

        # Successful
        await tracker.record_mtte("t1", "c1", 1000, success=True)
        await tracker.record_mtte("t2", "c2", 2000, success=True)

        # Failed - should be excluded
        await tracker.record_mtte("t3", "c3", 9999999, success=False, error="Error")

        stats = await tracker.get_mtte_stats()

        assert stats["count"] == 2
        assert stats["avg_ms"] == 1500  # Only successful measurements

    async def test_get_rsr_perfect(self):
        """RSR is 1.0 with all successes."""
        tracker = SLOTracker()

        for i in range(10):
            await tracker.record_rsr(
                thread_id=f"thread-{i}",
                checkpoint_id="ckpt-1",
                replay_mode="strict",
                success=True
            )

        rsr = await tracker.get_rsr()
        assert rsr == 1.0

    async def test_get_rsr_with_failures(self):
        """RSR calculates correctly with failures."""
        tracker = SLOTracker()

        # 98 successes
        for i in range(98):
            await tracker.record_rsr(f"t{i}", "c1", "strict", success=True)

        # 2 failures
        await tracker.record_rsr("t98", "c1", "strict", success=False)
        await tracker.record_rsr("t99", "c1", "strict", success=False)

        rsr = await tracker.get_rsr()
        assert rsr == 0.98

    async def test_get_rsr_by_mode(self):
        """RSR can be filtered by replay mode."""
        tracker = SLOTracker()

        # Strict: 100% success
        await tracker.record_rsr("t1", "c1", "strict", success=True)
        await tracker.record_rsr("t2", "c2", "strict", success=True)

        # Simulated: 50% success
        await tracker.record_rsr("t3", "c3", "simulated", success=True)
        await tracker.record_rsr("t4", "c4", "simulated", success=False)

        strict_rsr = await tracker.get_rsr(replay_mode="strict")
        simulated_rsr = await tracker.get_rsr(replay_mode="simulated")

        assert strict_rsr == 1.0
        assert simulated_rsr == 0.5

    async def test_get_report(self):
        """Can generate comprehensive report."""
        tracker = SLOTracker()

        # Record MTTE
        for duration in [1000, 2000, 3000]:
            await tracker.record_mtte(f"t{duration}", "c1", duration, success=True)

        # Record RSR
        for i in range(10):
            await tracker.record_rsr(f"t{i}", "c1", "strict", success=True)

        report = await tracker.get_report()

        assert report.mtte_avg_ms == 2000
        assert report.total_mtte_measurements == 3
        assert report.rsr == 1.0
        assert report.total_rsr_attempts == 10
        assert report.successful_replays == 10

    async def test_get_report_with_time_range(self):
        """Can generate report for time range."""
        tracker = SLOTracker()

        # Add old measurement manually
        old_mtte = MTTEMeasurement(
            thread_id="old",
            checkpoint_id="c1",
            duration_ms=9999,
            timestamp=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            success=True
        )
        tracker.mtte_measurements.append(old_mtte)

        # Add new measurement
        await tracker.record_mtte("new", "c2", 1000, success=True)

        # Get report from last hour
        since = datetime.now(timezone.utc) - timedelta(hours=1)
        report = await tracker.get_report(since=since)

        # Should only include new measurement
        assert report.total_mtte_measurements == 1
        assert report.mtte_avg_ms == 1000

    async def test_clear_measurements(self):
        """Can clear all measurements."""
        tracker = SLOTracker()

        await tracker.record_mtte("t1", "c1", 1000, success=True)
        await tracker.record_rsr("t1", "c1", "strict", success=True)

        await tracker.clear_measurements()

        assert len(tracker.mtte_measurements) == 0
        assert len(tracker.rsr_measurements) == 0

    async def test_clear_measurements_before(self):
        """Can clear measurements before a time."""
        tracker = SLOTracker()

        # Add old measurement
        old_mtte = MTTEMeasurement(
            thread_id="old",
            checkpoint_id="c1",
            duration_ms=9999,
            timestamp=(datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
            success=True
        )
        tracker.mtte_measurements.append(old_mtte)

        # Add new measurement
        await tracker.record_mtte("new", "c2", 1000, success=True)

        # Clear old measurements
        cutoff = datetime.now(timezone.utc) - timedelta(hours=1)
        await tracker.clear_measurements(before=cutoff)

        # Should only keep new measurement
        assert len(tracker.mtte_measurements) == 1
        assert tracker.mtte_measurements[0].thread_id == "new"
