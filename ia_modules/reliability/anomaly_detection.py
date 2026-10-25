"""
Anomaly detection for agent reliability metrics.

Detects unusual patterns in agent behavior using statistical methods
and threshold-based rules. Integrates with the Enterprise Agent
Reliability Framework (EARF) monitoring requirements.
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
import statistics
import logging


class AnomalyType(Enum):
    """Types of anomalies that can be detected."""
    SUDDEN_SPIKE = "sudden_spike"           # Metric increased dramatically
    SUDDEN_DROP = "sudden_drop"             # Metric decreased dramatically
    THRESHOLD_BREACH = "threshold_breach"   # Metric exceeded threshold
    PATTERN_CHANGE = "pattern_change"       # Statistical distribution changed
    COST_OVERRUN = "cost_overrun"          # Cost exceeded budget
    LATENCY_SPIKE = "latency_spike"        # Tool latency exceeded normal


class Severity(Enum):
    """Anomaly severity levels."""
    LOW = "low"           # Minor deviation, informational
    MEDIUM = "medium"     # Moderate deviation, investigate
    HIGH = "high"         # Significant deviation, action required
    CRITICAL = "critical" # Severe deviation, immediate action


@dataclass
class Anomaly:
    """
    Represents a detected anomaly.

    Attributes:
        type: Type of anomaly detected
        severity: Severity level
        metric_name: Name of affected metric
        current_value: Current metric value
        expected_value: Expected value based on baseline
        deviation: How much it deviated (percentage or absolute)
        timestamp: When anomaly was detected
        agent: Agent involved (if applicable)
        context: Additional context information
    """
    type: AnomalyType
    severity: Severity
    metric_name: str
    current_value: float
    expected_value: float
    deviation: float
    timestamp: datetime
    agent: Optional[str] = None
    context: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type.value,
            "severity": self.severity.value,
            "metric_name": self.metric_name,
            "current_value": self.current_value,
            "expected_value": self.expected_value,
            "deviation": self.deviation,
            "timestamp": self.timestamp.isoformat(),
            "agent": self.agent,
            "context": self.context
        }


@dataclass
class AnomalyThreshold:
    """
    Threshold configuration for anomaly detection.

    Attributes:
        metric_name: Name of metric to monitor
        max_value: Maximum allowed value (None = no limit)
        min_value: Minimum allowed value (None = no limit)
        max_deviation_percent: Maximum deviation from baseline (%)
        max_deviation_std: Maximum deviation in standard deviations
        severity: Severity to assign when threshold breached
    """
    metric_name: str
    max_value: Optional[float] = None
    min_value: Optional[float] = None
    max_deviation_percent: Optional[float] = None
    max_deviation_std: Optional[float] = None
    severity: Severity = Severity.MEDIUM


class AnomalyDetector:
    """
    Detect anomalies in agent reliability metrics.

    Uses multiple detection methods:
    - Threshold-based detection (static limits)
    - Statistical detection (Z-score, IQR)
    - Rate-of-change detection (sudden spikes/drops)
    - Pattern-based detection (distribution changes)

    Example:
        >>> detector = AnomalyDetector()
        >>>
        >>> # Configure thresholds based on EARF targets
        >>> detector.add_threshold(AnomalyThreshold(
        ...     metric_name="svr",
        ...     min_value=0.95,  # SVR target >95%
        ...     severity=Severity.HIGH
        ... ))
        >>>
        >>> # Record metric values over time
        >>> detector.record_value("svr", 0.98, agent="researcher")
        >>> detector.record_value("svr", 0.92, agent="researcher")  # Below threshold
        >>>
        >>> # Check for anomalies
        >>> anomalies = detector.detect_anomalies()
        >>> for anomaly in anomalies:
        ...     print(f"{anomaly.severity.value}: {anomaly.metric_name} = {anomaly.current_value}")
    """

    def __init__(
        self,
        baseline_window: int = 100,
        min_baseline_samples: int = 10,
        zscore_threshold: float = 3.0
    ):
        """
        Initialize anomaly detector.

        Args:
            baseline_window: Number of samples to use for baseline calculation
            min_baseline_samples: Minimum samples needed before detection
            zscore_threshold: Z-score threshold for statistical anomalies
        """
        self.baseline_window = baseline_window
        self.min_baseline_samples = min_baseline_samples
        self.zscore_threshold = zscore_threshold

        # Metric history: {metric_name: [(value, timestamp, agent), ...]}
        self._history: Dict[str, List[tuple]] = {}

        # Configured thresholds
        self._thresholds: Dict[str, AnomalyThreshold] = {}

        # Detected anomalies
        self._anomalies: List[Anomaly] = []

        # Callbacks for anomaly notifications
        self._callbacks: List[Callable[[Anomaly], None]] = []

        self.logger = logging.getLogger("AnomalyDetector")

    def add_threshold(self, threshold: AnomalyThreshold):
        """
        Add or update threshold configuration.

        Args:
            threshold: Threshold configuration
        """
        self._thresholds[threshold.metric_name] = threshold
        self.logger.info(f"Added threshold for {threshold.metric_name}")

    def remove_threshold(self, metric_name: str) -> bool:
        """
        Remove threshold configuration.

        Args:
            metric_name: Metric to remove threshold for

        Returns:
            True if threshold was removed, False if not found
        """
        if metric_name in self._thresholds:
            del self._thresholds[metric_name]
            self.logger.info(f"Removed threshold for {metric_name}")
            return True
        return False

    def record_value(
        self,
        metric_name: str,
        value: float,
        agent: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ):
        """
        Record a metric value for anomaly detection.

        Args:
            metric_name: Name of metric
            value: Metric value
            agent: Agent name (optional)
            timestamp: When value was recorded (default: now)
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        if metric_name not in self._history:
            self._history[metric_name] = []

        # Add to history
        self._history[metric_name].append((value, timestamp, agent))

        # Keep only recent values (sliding window)
        if len(self._history[metric_name]) > self.baseline_window * 2:
            self._history[metric_name] = self._history[metric_name][-self.baseline_window:]

    def detect_anomalies(
        self,
        metric_name: Optional[str] = None
    ) -> List[Anomaly]:
        """
        Detect anomalies in recorded metrics.

        Args:
            metric_name: Specific metric to check (None = check all)

        Returns:
            List of detected anomalies
        """
        anomalies: list[dict[str, Any]] = []

        # Determine which metrics to check
        metrics_to_check = [metric_name] if metric_name else list(self._history.keys())

        for metric in metrics_to_check:
            if metric not in self._history:
                continue

            # Get recent values
            history = self._history[metric]

            if len(history) < self.min_baseline_samples:
                continue  # Not enough data yet

            # Run detection methods
            anomalies.extend(self._check_threshold_breach(metric, history))
            anomalies.extend(self._check_statistical_anomaly(metric, history))
            anomalies.extend(self._check_rate_of_change(metric, history))

        # Store detected anomalies
        self._anomalies.extend(anomalies)

        # Trigger callbacks
        for anomaly in anomalies:
            for callback in self._callbacks:
                try:
                    callback(anomaly)
                except Exception as e:
                    self.logger.error(f"Anomaly callback failed: {e}")

        return anomalies

    def _check_threshold_breach(
        self,
        metric_name: str,
        history: List[tuple]
    ) -> List[Anomaly]:
        """Check for threshold breaches."""
        anomalies: list[dict[str, Any]] = []

        if metric_name not in self._thresholds:
            return anomalies

        threshold = self._thresholds[metric_name]
        current_value, current_time, agent = history[-1]

        # Check max threshold
        if threshold.max_value is not None and current_value > threshold.max_value:
            anomalies.append(Anomaly(
                type=AnomalyType.THRESHOLD_BREACH,
                severity=threshold.severity,
                metric_name=metric_name,
                current_value=current_value,
                expected_value=threshold.max_value,
                deviation=(current_value - threshold.max_value) / threshold.max_value * 100,
                timestamp=current_time,
                agent=agent,
                context={"threshold_type": "max", "threshold": threshold.max_value}
            ))

        # Check min threshold
        if threshold.min_value is not None and current_value < threshold.min_value:
            anomalies.append(Anomaly(
                type=AnomalyType.THRESHOLD_BREACH,
                severity=threshold.severity,
                metric_name=metric_name,
                current_value=current_value,
                expected_value=threshold.min_value,
                deviation=(threshold.min_value - current_value) / threshold.min_value * 100,
                timestamp=current_time,
                agent=agent,
                context={"threshold_type": "min", "threshold": threshold.min_value}
            ))

        return anomalies

    def _check_statistical_anomaly(
        self,
        metric_name: str,
        history: List[tuple]
    ) -> List[Anomaly]:
        """Check for statistical anomalies using Z-score."""
        anomalies: list[dict[str, Any]] = []

        if len(history) < self.min_baseline_samples:
            return anomalies

        # Calculate baseline statistics (excluding current value)
        baseline_values = [v for v, _, _ in history[:-1]]
        current_value, current_time, agent = history[-1]

        if len(baseline_values) < 2:
            return anomalies

        mean = statistics.mean(baseline_values)
        stdev = statistics.stdev(baseline_values)

        if stdev == 0:
            return anomalies  # No variation in baseline

        # Calculate Z-score
        zscore = abs((current_value - mean) / stdev)

        if zscore > self.zscore_threshold:
            # Determine severity based on Z-score magnitude
            if zscore > 5:
                severity = Severity.CRITICAL
            elif zscore > 4:
                severity = Severity.HIGH
            else:
                severity = Severity.MEDIUM

            # Determine if spike or drop
            if current_value > mean:
                anomaly_type = AnomalyType.SUDDEN_SPIKE
            else:
                anomaly_type = AnomalyType.SUDDEN_DROP

            anomalies.append(Anomaly(
                type=anomaly_type,
                severity=severity,
                metric_name=metric_name,
                current_value=current_value,
                expected_value=mean,
                deviation=zscore,
                timestamp=current_time,
                agent=agent,
                context={
                    "zscore": zscore,
                    "baseline_mean": mean,
                    "baseline_stdev": stdev,
                    "baseline_samples": len(baseline_values)
                }
            ))

        return anomalies

    def _check_rate_of_change(
        self,
        metric_name: str,
        history: List[tuple]
    ) -> List[Anomaly]:
        """Check for sudden rate-of-change anomalies."""
        anomalies: list[dict[str, Any]] = []

        if len(history) < 2:
            return anomalies

        # Compare last two values
        prev_value, prev_time, _ = history[-2]
        current_value, current_time, agent = history[-1]

        # Check if threshold configured with max_deviation_percent
        if metric_name in self._thresholds:
            threshold = self._thresholds[metric_name]

            if threshold.max_deviation_percent is not None and prev_value != 0:
                percent_change = abs((current_value - prev_value) / prev_value * 100)

                if percent_change > threshold.max_deviation_percent:
                    anomalies.append(Anomaly(
                        type=AnomalyType.PATTERN_CHANGE,
                        severity=threshold.severity,
                        metric_name=metric_name,
                        current_value=current_value,
                        expected_value=prev_value,
                        deviation=percent_change,
                        timestamp=current_time,
                        agent=agent,
                        context={
                            "percent_change": percent_change,
                            "threshold": threshold.max_deviation_percent
                        }
                    ))

        return anomalies

    def register_callback(self, callback: Callable[[Anomaly], None]):
        """
        Register callback for anomaly notifications.

        Args:
            callback: Function to call when anomaly detected
        """
        self._callbacks.append(callback)

    def get_anomalies(
        self,
        since: Optional[datetime] = None,
        severity: Optional[Severity] = None,
        metric_name: Optional[str] = None
    ) -> List[Anomaly]:
        """
        Retrieve detected anomalies with filtering.

        Args:
            since: Only return anomalies after this time
            severity: Filter by severity level
            metric_name: Filter by metric name

        Returns:
            Filtered list of anomalies
        """
        filtered = self._anomalies

        if since:
            filtered = [a for a in filtered if a.timestamp >= since]

        if severity:
            filtered = [a for a in filtered if a.severity == severity]

        if metric_name:
            filtered = [a for a in filtered if a.metric_name == metric_name]

        return filtered

    def clear_anomalies(self):
        """Clear all detected anomalies."""
        self._anomalies.clear()

    def get_baseline_stats(self, metric_name: str) -> Optional[Dict[str, float]]:
        """
        Get baseline statistics for a metric.

        Args:
            metric_name: Metric to get stats for

        Returns:
            Dict with mean, stdev, min, max, count
        """
        if metric_name not in self._history:
            return None

        values = [v for v, _, _ in self._history[metric_name]]

        if len(values) < 2:
            return None

        return {
            "mean": statistics.mean(values),
            "stdev": statistics.stdev(values) if len(values) > 1 else 0,
            "min": min(values),
            "max": max(values),
            "count": len(values)
        }
