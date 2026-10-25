"""
SLO Tracker

Measures and tracks Service Level Objectives for agent reliability:
- MTTE (Mean Time to Explain): Time to reconstruct any decision
- RSR (Replay Success Rate): % of decisions that can be replayed
"""

from dataclasses import dataclass
from typing import Dict, List, Optional
from datetime import datetime, timezone
import logging


@dataclass
class MTTEMeasurement:
    """Single MTTE measurement."""
    thread_id: str
    checkpoint_id: str
    duration_ms: int
    timestamp: str
    success: bool
    error: Optional[str] = None


@dataclass
class RSRMeasurement:
    """Single RSR measurement."""
    thread_id: str
    checkpoint_id: str
    replay_mode: str
    success: bool
    timestamp: str
    error: Optional[str] = None


@dataclass
class SLOReport:
    """SLO compliance report."""
    period_start: datetime
    period_end: datetime

    # MTTE metrics
    mtte_avg_ms: float
    mtte_p50_ms: float
    mtte_p95_ms: float
    mtte_p99_ms: float

    # RSR metrics
    rsr: float

    # Defaults
    mtte_target_ms: int = 300000  # 5 minutes
    total_mtte_measurements: int = 0
    rsr_target: float = 0.99  # 99%
    total_rsr_attempts: int = 0
    successful_replays: int = 0

    def is_mtte_compliant(self) -> bool:
        """Check if MTTE meets SLO target."""
        return self.mtte_p95_ms <= self.mtte_target_ms

    def is_rsr_compliant(self) -> bool:
        """Check if RSR meets SLO target."""
        return self.rsr >= self.rsr_target

    def is_compliant(self) -> bool:
        """Check if all SLOs are met."""
        return self.is_mtte_compliant() and self.is_rsr_compliant()

    def get_violations(self) -> List[str]:
        """Get list of SLO violations."""
        violations = []

        if not self.is_mtte_compliant():
            violations.append(
                f"MTTE P95 {self.mtte_p95_ms:.0f}ms exceeds target {self.mtte_target_ms}ms"
            )

        if not self.is_rsr_compliant():
            violations.append(
                f"RSR {self.rsr:.2%} below target {self.rsr_target:.0%}"
            )

        return violations


class SLOTracker:
    """
    Track Service Level Objectives for agent reliability.

    Measures two key SLOs:
    - MTTE (Mean Time to Explain): How quickly can we reconstruct any decision?
    - RSR (Replay Success Rate): What % of decisions can be successfully replayed?

    Example:
        >>> tracker = SLOTracker()
        >>>
        >>> # Measure MTTE
        >>> start = time.time()
        >>> trail = await builder.build_trail(thread_id)
        >>> duration_ms = int((time.time() - start) * 1000)
        >>> await tracker.record_mtte(thread_id, checkpoint_id, duration_ms, success=True)
        >>>
        >>> # Measure RSR
        >>> result = await replayer.strict_replay(trail)
        >>> await tracker.record_rsr(thread_id, checkpoint_id, "strict", result.success)
        >>>
        >>> # Get report
        >>> report = await tracker.get_report()
        >>> print(f"MTTE P95: {report.mtte_p95_ms:.0f}ms (target: {report.mtte_target_ms}ms)")
        >>> print(f"RSR: {report.rsr:.2%} (target: {report.rsr_target:.0%})")
        >>> print(f"Compliant: {report.is_compliant()}")
    """

    def __init__(self):
        """Initialize SLO tracker."""
        self.mtte_measurements: List[MTTEMeasurement] = []
        self.rsr_measurements: List[RSRMeasurement] = []
        self.logger = logging.getLogger("SLOTracker")

    async def record_mtte(
        self,
        thread_id: str,
        checkpoint_id: str,
        duration_ms: int,
        success: bool,
        error: Optional[str] = None
    ):
        """
        Record an MTTE measurement.

        Args:
            thread_id: Thread ID
            checkpoint_id: Checkpoint ID
            duration_ms: Time taken to explain decision (milliseconds)
            success: Whether explanation succeeded
            error: Error message if failed
        """
        measurement = MTTEMeasurement(
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            duration_ms=duration_ms,
            timestamp=datetime.now(timezone.utc).isoformat(),
            success=success,
            error=error
        )

        self.mtte_measurements.append(measurement)

        if not success:
            self.logger.warning(
                f"MTTE measurement failed for {thread_id}/{checkpoint_id}: {error}"
            )
        elif duration_ms > 300000:  # 5 minutes
            self.logger.warning(
                f"MTTE {duration_ms}ms exceeds 5min target for {thread_id}/{checkpoint_id}"
            )

    async def record_rsr(
        self,
        thread_id: str,
        checkpoint_id: str,
        replay_mode: str,
        success: bool,
        error: Optional[str] = None
    ):
        """
        Record an RSR measurement.

        Args:
            thread_id: Thread ID
            checkpoint_id: Checkpoint ID
            replay_mode: Replay mode used (strict, simulated, counterfactual)
            success: Whether replay succeeded
            error: Error message if failed
        """
        measurement = RSRMeasurement(
            thread_id=thread_id,
            checkpoint_id=checkpoint_id,
            replay_mode=replay_mode,
            success=success,
            timestamp=datetime.now(timezone.utc).isoformat(),
            error=error
        )

        self.rsr_measurements.append(measurement)

        if not success:
            self.logger.warning(
                f"RSR replay failed for {thread_id}/{checkpoint_id} ({replay_mode}): {error}"
            )

    async def get_mtte_stats(
        self,
        since: Optional[datetime] = None
    ) -> Dict[str, float]:
        """
        Get MTTE statistics.

        Args:
            since: Only include measurements after this time

        Returns:
            Dictionary with avg, p50, p95, p99 in milliseconds
        """
        measurements = self.mtte_measurements

        if since:
            measurements = [
                m for m in measurements
                if datetime.fromisoformat(m.timestamp) >= since
            ]

        # Only consider successful measurements
        successful = [m for m in measurements if m.success]

        if not successful:
            return {
                "avg_ms": 0.0,
                "p50_ms": 0.0,
                "p95_ms": 0.0,
                "p99_ms": 0.0,
                "count": 0
            }

        durations = sorted([m.duration_ms for m in successful])
        n = len(durations)

        return {
            "avg_ms": sum(durations) / n,
            "p50_ms": durations[int(n * 0.50)] if n > 0 else 0.0,
            "p95_ms": durations[int(n * 0.95)] if n > 0 else 0.0,
            "p99_ms": durations[int(n * 0.99)] if n > 0 else 0.0,
            "count": n
        }

    async def get_rsr(
        self,
        replay_mode: Optional[str] = None,
        since: Optional[datetime] = None
    ) -> float:
        """
        Get Replay Success Rate.

        Args:
            replay_mode: Filter by replay mode (optional)
            since: Only include measurements after this time

        Returns:
            RSR as a float (0.0 to 1.0)
        """
        measurements = self.rsr_measurements

        if replay_mode:
            measurements = [m for m in measurements if m.replay_mode == replay_mode]

        if since:
            measurements = [
                m for m in measurements
                if datetime.fromisoformat(m.timestamp) >= since
            ]

        if not measurements:
            return 1.0  # No failures if no measurements

        successful = sum(1 for m in measurements if m.success)
        return successful / len(measurements)

    async def get_report(
        self,
        since: Optional[datetime] = None
    ) -> SLOReport:
        """
        Generate comprehensive SLO report.

        Args:
            since: Only include measurements after this time

        Returns:
            SLO compliance report
        """
        mtte_stats = await self.get_mtte_stats(since=since)
        rsr = await self.get_rsr(since=since)

        # Count total attempts
        measurements = self.rsr_measurements
        if since:
            measurements = [
                m for m in measurements
                if datetime.fromisoformat(m.timestamp) >= since
            ]

        total_rsr_attempts = len(measurements)
        successful_replays = sum(1 for m in measurements if m.success)

        return SLOReport(
            period_start=since or datetime.min,
            period_end=datetime.now(timezone.utc),
            mtte_avg_ms=mtte_stats["avg_ms"],
            mtte_p50_ms=mtte_stats["p50_ms"],
            mtte_p95_ms=mtte_stats["p95_ms"],
            mtte_p99_ms=mtte_stats["p99_ms"],
            total_mtte_measurements=int(mtte_stats["count"]),
            rsr=rsr,
            total_rsr_attempts=total_rsr_attempts,
            successful_replays=successful_replays
        )

    async def clear_measurements(self, before: Optional[datetime] = None):
        """
        Clear old measurements.

        Args:
            before: Clear measurements before this time (default: all)
        """
        if before is None:
            self.mtte_measurements.clear()
            self.rsr_measurements.clear()
        else:
            self.mtte_measurements = [
                m for m in self.mtte_measurements
                if datetime.fromisoformat(m.timestamp) >= before
            ]
            self.rsr_measurements = [
                m for m in self.rsr_measurements
                if datetime.fromisoformat(m.timestamp) >= before
            ]
