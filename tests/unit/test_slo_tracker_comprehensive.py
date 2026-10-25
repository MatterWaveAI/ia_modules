"""Comprehensive tests for reliability.slo_tracker module"""

import pytest
from datetime import datetime, timezone, timedelta
from ia_modules.reliability.slo_tracker import (
    MTTEMeasurement,
    RSRMeasurement,
    SLOReport,
    SLOTracker
)


class TestMTTEMeasurement:
    """Test MTTEMeasurement dataclass"""

    def test_init(self):
        """Test MTTE measurement creation"""
        measurement = MTTEMeasurement(
            thread_id="thread-123",
            checkpoint_id="cp-123",
            duration_ms=1500,
            timestamp="2024-01-01T00:00:00Z",
            success=True
        )

        assert measurement.thread_id == "thread-123"
        assert measurement.checkpoint_id == "cp-123"
        assert measurement.duration_ms == 1500
        assert measurement.success is True
        assert measurement.error is None

    def test_init_with_error(self):
        """Test MTTE measurement with error"""
        measurement = MTTEMeasurement(
            thread_id="thread-123",
            checkpoint_id="cp-123",
            duration_ms=0,
            timestamp="2024-01-01",
            success=False,
            error="Failed to build trail"
        )

        assert measurement.success is False
        assert measurement.error == "Failed to build trail"


class TestRSRMeasurement:
    """Test RSRMeasurement dataclass"""

    def test_init(self):
        """Test RSR measurement creation"""
        measurement = RSRMeasurement(
            thread_id="thread-123",
            checkpoint_id="cp-123",
            replay_mode="strict",
            success=True,
            timestamp="2024-01-01T00:00:00Z"
        )

        assert measurement.thread_id == "thread-123"
        assert measurement.replay_mode == "strict"
        assert measurement.success is True
        assert measurement.error is None

    def test_init_with_error(self):
        """Test RSR measurement with error"""
        measurement = RSRMeasurement(
            thread_id="thread-123",
            checkpoint_id="cp-123",
            replay_mode="simulated",
            success=False,
            timestamp="2024-01-01",
            error="Replay failed"
        )

        assert measurement.success is False
        assert measurement.error == "Replay failed"


class TestSLOReport:
    """Test SLOReport dataclass"""

    def test_init(self):
        """Test SLO report creation"""
        start = datetime.now(timezone.utc)
        end = start + timedelta(hours=1)

        report = SLOReport(
            period_start=start,
            period_end=end,
            mtte_avg_ms=100000.0,
            mtte_p50_ms=80000.0,
            mtte_p95_ms=250000.0,
            mtte_p99_ms=280000.0,
            rsr=0.995
        )

        assert report.mtte_avg_ms == 100000.0
        assert report.rsr == 0.995

    def test_is_mtte_compliant_pass(self):
        """Test MTTE compliance check passing"""
        report = SLOReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            mtte_avg_ms=100000.0,
            mtte_p50_ms=80000.0,
            mtte_p95_ms=250000.0,
            mtte_p99_ms=280000.0,
            rsr=0.995
        )

        assert report.is_mtte_compliant() is True

    def test_is_mtte_compliant_fail(self):
        """Test MTTE compliance check failing"""
        report = SLOReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            mtte_avg_ms=400000.0,
            mtte_p50_ms=350000.0,
            mtte_p95_ms=450000.0,
            mtte_p99_ms=500000.0,
            rsr=0.995
        )

        assert report.is_mtte_compliant() is False

    def test_is_rsr_compliant_pass(self):
        """Test RSR compliance check passing"""
        report = SLOReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            mtte_avg_ms=100000.0,
            mtte_p50_ms=80000.0,
            mtte_p95_ms=250000.0,
            mtte_p99_ms=280000.0,
            rsr=0.995
        )

        assert report.is_rsr_compliant() is True

    def test_is_rsr_compliant_fail(self):
        """Test RSR compliance check failing"""
        report = SLOReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            mtte_avg_ms=100000.0,
            mtte_p50_ms=80000.0,
            mtte_p95_ms=250000.0,
            mtte_p99_ms=280000.0,
            rsr=0.95
        )

        assert report.is_rsr_compliant() is False

    def test_is_compliant_all_pass(self):
        """Test overall compliance with all metrics passing"""
        report = SLOReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            mtte_avg_ms=100000.0,
            mtte_p50_ms=80000.0,
            mtte_p95_ms=250000.0,
            mtte_p99_ms=280000.0,
            rsr=0.995
        )

        assert report.is_compliant() is True

    def test_is_compliant_mtte_fail(self):
        """Test overall compliance with MTTE failing"""
        report = SLOReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            mtte_avg_ms=400000.0,
            mtte_p50_ms=350000.0,
            mtte_p95_ms=450000.0,
            mtte_p99_ms=500000.0,
            rsr=0.995
        )

        assert report.is_compliant() is False

    def test_get_violations_none(self):
        """Test no violations"""
        report = SLOReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            mtte_avg_ms=100000.0,
            mtte_p50_ms=80000.0,
            mtte_p95_ms=250000.0,
            mtte_p99_ms=280000.0,
            rsr=0.995
        )

        violations = report.get_violations()
        assert len(violations) == 0

    def test_get_violations_mtte(self):
        """Test MTTE violation"""
        report = SLOReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            mtte_avg_ms=400000.0,
            mtte_p50_ms=350000.0,
            mtte_p95_ms=450000.0,
            mtte_p99_ms=500000.0,
            rsr=0.995
        )

        violations = report.get_violations()
        assert len(violations) == 1
        assert "MTTE" in violations[0]

    def test_get_violations_rsr(self):
        """Test RSR violation"""
        report = SLOReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            mtte_avg_ms=100000.0,
            mtte_p50_ms=80000.0,
            mtte_p95_ms=250000.0,
            mtte_p99_ms=280000.0,
            rsr=0.95
        )

        violations = report.get_violations()
        assert len(violations) == 1
        assert "RSR" in violations[0]

    def test_get_violations_both(self):
        """Test both violations"""
        report = SLOReport(
            period_start=datetime.now(timezone.utc),
            period_end=datetime.now(timezone.utc),
            mtte_avg_ms=400000.0,
            mtte_p50_ms=350000.0,
            mtte_p95_ms=450000.0,
            mtte_p99_ms=500000.0,
            rsr=0.95
        )

        violations = report.get_violations()
        assert len(violations) == 2


class TestSLOTracker:
    """Test SLOTracker class"""

    def test_init(self):
        """Test tracker initialization"""
        tracker = SLOTracker()
        assert len(tracker.mtte_measurements) == 0
        assert len(tracker.rsr_measurements) == 0

    @pytest.mark.asyncio
    async def test_record_mtte_success(self):
        """Test recording successful MTTE measurement"""
        tracker = SLOTracker()

        await tracker.record_mtte(
            thread_id="thread-123",
            checkpoint_id="cp-123",
            duration_ms=150000,
            success=True
        )

        assert len(tracker.mtte_measurements) == 1
        measurement = tracker.mtte_measurements[0]
        assert measurement.thread_id == "thread-123"
        assert measurement.duration_ms == 150000
        assert measurement.success is True

    @pytest.mark.asyncio
    async def test_record_mtte_failure(self):
        """Test recording failed MTTE measurement"""
        tracker = SLOTracker()

        await tracker.record_mtte(
            thread_id="thread-123",
            checkpoint_id="cp-123",
            duration_ms=0,
            success=False,
            error="Build failed"
        )

        assert len(tracker.mtte_measurements) == 1
        measurement = tracker.mtte_measurements[0]
        assert measurement.success is False
        assert measurement.error == "Build failed"

    @pytest.mark.asyncio
    async def test_record_mtte_slow(self):
        """Test recording slow MTTE (triggers warning)"""
        tracker = SLOTracker()

        await tracker.record_mtte(
            thread_id="thread-123",
            checkpoint_id="cp-123",
            duration_ms=350000,
            success=True
        )

        assert len(tracker.mtte_measurements) == 1

    @pytest.mark.asyncio
    async def test_record_rsr_success(self):
        """Test recording successful RSR measurement"""
        tracker = SLOTracker()

        await tracker.record_rsr(
            thread_id="thread-123",
            checkpoint_id="cp-123",
            replay_mode="strict",
            success=True
        )

        assert len(tracker.rsr_measurements) == 1
        measurement = tracker.rsr_measurements[0]
        assert measurement.replay_mode == "strict"
        assert measurement.success is True

    @pytest.mark.asyncio
    async def test_record_rsr_failure(self):
        """Test recording failed RSR measurement"""
        tracker = SLOTracker()

        await tracker.record_rsr(
            thread_id="thread-123",
            checkpoint_id="cp-123",
            replay_mode="simulated",
            success=False,
            error="Replay failed"
        )

        assert len(tracker.rsr_measurements) == 1
        measurement = tracker.rsr_measurements[0]
        assert measurement.success is False

    @pytest.mark.asyncio
    async def test_get_mtte_stats_no_data(self):
        """Test MTTE stats with no data"""
        tracker = SLOTracker()

        stats = await tracker.get_mtte_stats()

        assert stats["avg_ms"] == 0.0
        assert stats["p50_ms"] == 0.0
        assert stats["p95_ms"] == 0.0
        assert stats["p99_ms"] == 0.0
        assert stats["count"] == 0

    @pytest.mark.asyncio
    async def test_get_mtte_stats_single_measurement(self):
        """Test MTTE stats with single measurement"""
        tracker = SLOTracker()

        await tracker.record_mtte("t1", "c1", 150000, True)

        stats = await tracker.get_mtte_stats()

        assert stats["avg_ms"] == 150000.0
        assert stats["p50_ms"] == 150000.0
        assert stats["count"] == 1

    @pytest.mark.asyncio
    async def test_get_mtte_stats_multiple_measurements(self):
        """Test MTTE stats with multiple measurements"""
        tracker = SLOTracker()

        await tracker.record_mtte("t1", "c1", 100000, True)
        await tracker.record_mtte("t2", "c2", 200000, True)
        await tracker.record_mtte("t3", "c3", 150000, True)

        stats = await tracker.get_mtte_stats()

        assert stats["avg_ms"] == 150000.0
        assert stats["count"] == 3

    @pytest.mark.asyncio
    async def test_get_mtte_stats_ignore_failures(self):
        """Test MTTE stats ignores failed measurements"""
        tracker = SLOTracker()

        await tracker.record_mtte("t1", "c1", 100000, True)
        await tracker.record_mtte("t2", "c2", 0, False)

        stats = await tracker.get_mtte_stats()

        assert stats["count"] == 1
        assert stats["avg_ms"] == 100000.0

    @pytest.mark.asyncio
    async def test_get_mtte_stats_with_since(self):
        """Test MTTE stats filtered by time"""
        tracker = SLOTracker()

        await tracker.record_mtte("t1", "c1", 100000, True)

        future = datetime.now(timezone.utc) + timedelta(hours=1)
        stats = await tracker.get_mtte_stats(since=future)

        assert stats["count"] == 0

    @pytest.mark.asyncio
    async def test_get_rsr_no_data(self):
        """Test RSR with no data"""
        tracker = SLOTracker()

        rsr = await tracker.get_rsr()

        assert rsr == 1.0

    @pytest.mark.asyncio
    async def test_get_rsr_all_success(self):
        """Test RSR with all successes"""
        tracker = SLOTracker()

        await tracker.record_rsr("t1", "c1", "strict", True)
        await tracker.record_rsr("t2", "c2", "strict", True)

        rsr = await tracker.get_rsr()

        assert rsr == 1.0

    @pytest.mark.asyncio
    async def test_get_rsr_with_failures(self):
        """Test RSR with some failures"""
        tracker = SLOTracker()

        await tracker.record_rsr("t1", "c1", "strict", True)
        await tracker.record_rsr("t2", "c2", "strict", False)
        await tracker.record_rsr("t3", "c3", "strict", True)

        rsr = await tracker.get_rsr()

        assert rsr == 2.0 / 3.0

    @pytest.mark.asyncio
    async def test_get_rsr_filter_by_mode(self):
        """Test RSR filtered by replay mode"""
        tracker = SLOTracker()

        await tracker.record_rsr("t1", "c1", "strict", True)
        await tracker.record_rsr("t2", "c2", "simulated", False)

        rsr = await tracker.get_rsr(replay_mode="strict")

        assert rsr == 1.0

    @pytest.mark.asyncio
    async def test_get_rsr_with_since(self):
        """Test RSR filtered by time"""
        tracker = SLOTracker()

        await tracker.record_rsr("t1", "c1", "strict", True)

        future = datetime.now(timezone.utc) + timedelta(hours=1)
        rsr = await tracker.get_rsr(since=future)

        assert rsr == 1.0

    @pytest.mark.asyncio
    async def test_get_report_no_data(self):
        """Test report with no data"""
        tracker = SLOTracker()

        report = await tracker.get_report()

        assert report.mtte_avg_ms == 0.0
        assert report.rsr == 1.0
        assert report.total_mtte_measurements == 0
        assert report.total_rsr_attempts == 0

    @pytest.mark.asyncio
    async def test_get_report_with_data(self):
        """Test report with data"""
        tracker = SLOTracker()

        await tracker.record_mtte("t1", "c1", 150000, True)
        await tracker.record_mtte("t2", "c2", 200000, True)

        await tracker.record_rsr("t1", "c1", "strict", True)
        await tracker.record_rsr("t2", "c2", "strict", True)
        await tracker.record_rsr("t3", "c3", "strict", False)

        report = await tracker.get_report()

        assert report.total_mtte_measurements == 2
        assert report.total_rsr_attempts == 3
        assert report.successful_replays == 2
        assert report.rsr == 2.0 / 3.0

    @pytest.mark.asyncio
    async def test_get_report_with_since(self):
        """Test report filtered by time"""
        tracker = SLOTracker()

        await tracker.record_mtte("t1", "c1", 150000, True)

        future = datetime.now(timezone.utc) + timedelta(hours=1)
        report = await tracker.get_report(since=future)

        assert report.total_mtte_measurements == 0

    @pytest.mark.asyncio
    async def test_clear_measurements_all(self):
        """Test clearing all measurements"""
        tracker = SLOTracker()

        await tracker.record_mtte("t1", "c1", 150000, True)
        await tracker.record_rsr("t1", "c1", "strict", True)

        await tracker.clear_measurements()

        assert len(tracker.mtte_measurements) == 0
        assert len(tracker.rsr_measurements) == 0

    @pytest.mark.asyncio
    async def test_clear_measurements_before(self):
        """Test clearing old measurements"""
        tracker = SLOTracker()

        await tracker.record_mtte("t1", "c1", 150000, True)
        await tracker.record_rsr("t1", "c1", "strict", True)

        # Clear measurements older than now (should clear the ones we just added)
        past = datetime.now(timezone.utc) - timedelta(hours=1)
        await tracker.clear_measurements(before=past)

        # Measurements recorded now should NOT be cleared
        assert len(tracker.mtte_measurements) == 1
        assert len(tracker.rsr_measurements) == 1

    @pytest.mark.asyncio
    async def test_percentile_calculation(self):
        """Test percentile calculation accuracy"""
        tracker = SLOTracker()

        # Add measurements: 100ms, 200ms, 300ms, 400ms, 500ms
        for i in range(1, 6):
            await tracker.record_mtte(f"t{i}", f"c{i}", i * 100000, True)

        stats = await tracker.get_mtte_stats()

        assert stats["p50_ms"] == 300000  # Median
        assert stats["count"] == 5

    @pytest.mark.asyncio
    async def test_multiple_replay_modes(self):
        """Test RSR with multiple replay modes"""
        tracker = SLOTracker()

        await tracker.record_rsr("t1", "c1", "strict", True)
        await tracker.record_rsr("t2", "c2", "simulated", True)
        await tracker.record_rsr("t3", "c3", "counterfactual", False)

        strict_rsr = await tracker.get_rsr(replay_mode="strict")
        simulated_rsr = await tracker.get_rsr(replay_mode="simulated")
        overall_rsr = await tracker.get_rsr()

        assert strict_rsr == 1.0
        assert simulated_rsr == 1.0
        assert overall_rsr == 2.0 / 3.0
