"""Tests for anomaly detection."""

from datetime import datetime, timedelta, timezone

from ia_modules.reliability.anomaly_detection import (
    AnomalyDetector,
    AnomalyThreshold,
    AnomalyType,
    Severity,
    Anomaly
)


def test_anomaly_detector_creation():
    """Test creating anomaly detector."""
    detector = AnomalyDetector()

    assert detector.baseline_window == 100
    assert detector.min_baseline_samples == 10
    assert detector.zscore_threshold == 3.0


def test_add_threshold():
    """Test adding threshold configuration."""
    detector = AnomalyDetector()

    threshold = AnomalyThreshold(
        metric_name="svr",
        min_value=0.95,
        severity=Severity.HIGH
    )

    detector.add_threshold(threshold)

    assert "svr" in detector._thresholds
    assert detector._thresholds["svr"].min_value == 0.95


def test_remove_threshold():
    """Test removing threshold configuration."""
    detector = AnomalyDetector()

    threshold = AnomalyThreshold(metric_name="svr", min_value=0.95)
    detector.add_threshold(threshold)

    result = detector.remove_threshold("svr")
    assert result is True
    assert "svr" not in detector._thresholds

    # Try removing non-existent threshold
    result = detector.remove_threshold("nonexistent")
    assert result is False


def test_record_value():
    """Test recording metric values."""
    detector = AnomalyDetector()

    detector.record_value("svr", 0.98, agent="researcher")
    detector.record_value("svr", 0.97, agent="researcher")

    assert "svr" in detector._history
    assert len(detector._history["svr"]) == 2


def test_threshold_breach_max():
    """Test detecting threshold breach (max)."""
    detector = AnomalyDetector(min_baseline_samples=2)

    # Add threshold
    detector.add_threshold(AnomalyThreshold(
        metric_name="cr",
        max_value=0.10,  # CR target <10%
        severity=Severity.HIGH
    ))

    # Record normal values
    detector.record_value("cr", 0.05)
    detector.record_value("cr", 0.06)

    # Record breach
    detector.record_value("cr", 0.15)  # Exceeds threshold

    anomalies = detector.detect_anomalies()

    # Should detect threshold breach (and possibly statistical anomaly too)
    assert len(anomalies) >= 1
    threshold_anomalies = [a for a in anomalies if a.type == AnomalyType.THRESHOLD_BREACH]
    assert len(threshold_anomalies) >= 1
    assert threshold_anomalies[0].severity == Severity.HIGH
    assert threshold_anomalies[0].current_value == 0.15
    assert threshold_anomalies[0].expected_value == 0.10


def test_threshold_breach_min():
    """Test detecting threshold breach (min)."""
    detector = AnomalyDetector(min_baseline_samples=2)

    # Add threshold
    detector.add_threshold(AnomalyThreshold(
        metric_name="svr",
        min_value=0.95,  # SVR target >95%
        severity=Severity.HIGH
    ))

    # Record normal values
    detector.record_value("svr", 0.98)
    detector.record_value("svr", 0.97)

    # Record breach
    detector.record_value("svr", 0.92)  # Below threshold

    anomalies = detector.detect_anomalies()

    # Should detect threshold breach (and possibly statistical anomaly too)
    assert len(anomalies) >= 1
    threshold_anomalies = [a for a in anomalies if a.type == AnomalyType.THRESHOLD_BREACH]
    assert len(threshold_anomalies) >= 1
    assert threshold_anomalies[0].severity == Severity.HIGH
    assert threshold_anomalies[0].current_value == 0.92


def test_statistical_anomaly_spike():
    """Test detecting statistical anomaly (spike)."""
    detector = AnomalyDetector(min_baseline_samples=5, zscore_threshold=3.0)

    # Record stable baseline
    for i in range(10):
        detector.record_value("latency", 100.0 + i)  # ~100ms

    # Record spike
    detector.record_value("latency", 500.0)  # Huge spike

    anomalies = detector.detect_anomalies()

    assert len(anomalies) > 0
    spike_anomalies = [a for a in anomalies if a.type == AnomalyType.SUDDEN_SPIKE]
    assert len(spike_anomalies) > 0
    assert spike_anomalies[0].current_value == 500.0


def test_statistical_anomaly_drop():
    """Test detecting statistical anomaly (drop)."""
    detector = AnomalyDetector(min_baseline_samples=5, zscore_threshold=3.0)

    # Record stable baseline
    for i in range(10):
        detector.record_value("success_rate", 0.98 + i * 0.001)

    # Record drop
    detector.record_value("success_rate", 0.50)  # Sudden drop

    anomalies = detector.detect_anomalies()

    assert len(anomalies) > 0
    drop_anomalies = [a for a in anomalies if a.type == AnomalyType.SUDDEN_DROP]
    assert len(drop_anomalies) > 0
    assert drop_anomalies[0].current_value == 0.50


def test_rate_of_change_detection():
    """Test detecting rate-of-change anomalies."""
    detector = AnomalyDetector(min_baseline_samples=2)

    # Add threshold with max deviation
    detector.add_threshold(AnomalyThreshold(
        metric_name="cost",
        max_deviation_percent=50.0,  # Max 50% change
        severity=Severity.MEDIUM
    ))

    # Record baseline
    detector.record_value("cost", 100.0)

    # Record large change
    detector.record_value("cost", 200.0)  # 100% change

    anomalies = detector.detect_anomalies()

    pattern_anomalies = [a for a in anomalies if a.type == AnomalyType.PATTERN_CHANGE]
    assert len(pattern_anomalies) > 0
    assert pattern_anomalies[0].deviation > 50.0


def test_insufficient_baseline():
    """Test that statistical detection requires minimum samples."""
    detector = AnomalyDetector(min_baseline_samples=10)

    # Record only a few values (not enough for statistical detection)
    for i in range(5):
        detector.record_value("svr", 0.98)

    detector.record_value("svr", 0.50)  # Huge drop

    anomalies = detector.detect_anomalies()

    # Should NOT detect statistical anomaly (insufficient baseline)
    statistical_anomalies = [a for a in anomalies if a.type in [AnomalyType.SUDDEN_SPIKE, AnomalyType.SUDDEN_DROP]]
    assert len(statistical_anomalies) == 0


def test_multiple_metrics():
    """Test detecting anomalies across multiple metrics."""
    detector = AnomalyDetector(min_baseline_samples=5)

    # Add thresholds for multiple metrics
    detector.add_threshold(AnomalyThreshold(
        metric_name="svr",
        min_value=0.95
    ))
    detector.add_threshold(AnomalyThreshold(
        metric_name="cr",
        max_value=0.10
    ))

    # Record values for both metrics
    for i in range(10):
        detector.record_value("svr", 0.98)
        detector.record_value("cr", 0.05)

    # Record anomalies in both
    detector.record_value("svr", 0.90)  # Below threshold
    detector.record_value("cr", 0.15)  # Above threshold

    anomalies = detector.detect_anomalies()

    # Should detect anomalies in both metrics
    assert len(anomalies) >= 2
    svr_anomalies = [a for a in anomalies if a.metric_name == "svr"]
    cr_anomalies = [a for a in anomalies if a.metric_name == "cr"]
    assert len(svr_anomalies) > 0
    assert len(cr_anomalies) > 0


def test_anomaly_callback():
    """Test anomaly notification callbacks."""
    detector = AnomalyDetector(min_baseline_samples=2)

    # Track callback invocations
    detected_anomalies = []

    def callback(anomaly: Anomaly):
        detected_anomalies.append(anomaly)

    detector.register_callback(callback)

    # Add threshold
    detector.add_threshold(AnomalyThreshold(
        metric_name="svr",
        min_value=0.95
    ))

    # Record normal then anomaly
    detector.record_value("svr", 0.98)
    detector.record_value("svr", 0.90)

    detector.detect_anomalies()

    # Callback should have been invoked
    assert len(detected_anomalies) > 0
    assert detected_anomalies[0].metric_name == "svr"


def test_get_anomalies_filtering():
    """Test retrieving anomalies with filters."""
    detector = AnomalyDetector(min_baseline_samples=2)

    detector.add_threshold(AnomalyThreshold(
        metric_name="metric1",
        max_value=10.0,
        severity=Severity.HIGH
    ))
    detector.add_threshold(AnomalyThreshold(
        metric_name="metric2",
        max_value=20.0,
        severity=Severity.LOW
    ))

    # Record anomalies at different times
    now = datetime.now(timezone.utc)
    detector.record_value("metric1", 5.0, timestamp=now - timedelta(hours=2))
    detector.record_value("metric1", 15.0, timestamp=now - timedelta(hours=1))  # Anomaly

    detector.record_value("metric2", 10.0, timestamp=now)
    detector.record_value("metric2", 30.0, timestamp=now)  # Anomaly

    detector.detect_anomalies()

    # Filter by severity
    high_severity = detector.get_anomalies(severity=Severity.HIGH)
    assert all(a.severity == Severity.HIGH for a in high_severity)

    # Filter by metric
    metric1_anomalies = detector.get_anomalies(metric_name="metric1")
    assert all(a.metric_name == "metric1" for a in metric1_anomalies)

    # Filter by time
    recent = detector.get_anomalies(since=now - timedelta(minutes=30))
    assert all(a.timestamp >= now - timedelta(minutes=30) for a in recent)


def test_clear_anomalies():
    """Test clearing detected anomalies."""
    detector = AnomalyDetector(min_baseline_samples=2)

    detector.add_threshold(AnomalyThreshold(
        metric_name="svr",
        min_value=0.95
    ))

    detector.record_value("svr", 0.98)
    detector.record_value("svr", 0.90)

    detector.detect_anomalies()
    assert len(detector._anomalies) > 0

    detector.clear_anomalies()
    assert len(detector._anomalies) == 0


def test_get_baseline_stats():
    """Test retrieving baseline statistics."""
    detector = AnomalyDetector()

    # Record values
    for i in range(10):
        detector.record_value("latency", 100.0 + i)

    stats = detector.get_baseline_stats("latency")

    assert stats is not None
    assert stats["count"] == 10
    assert stats["min"] == 100.0
    assert stats["max"] == 109.0
    assert 100.0 < stats["mean"] < 110.0

    # Non-existent metric
    stats = detector.get_baseline_stats("nonexistent")
    assert stats is None


def test_severity_escalation():
    """Test that severity escalates with Z-score magnitude."""
    detector = AnomalyDetector(min_baseline_samples=5, zscore_threshold=3.0)

    # Record baseline with some variation (not all same value)
    for i in range(20):
        detector.record_value("metric", 100.0 + i)  # 100 to 119

    # Record extreme spike (high Z-score)
    detector.record_value("metric", 1000.0)

    anomalies = detector.detect_anomalies()

    spike_anomalies = [a for a in anomalies if a.type == AnomalyType.SUDDEN_SPIKE]
    assert len(spike_anomalies) > 0

    # Should be high or critical severity due to extreme Z-score
    assert spike_anomalies[0].severity in [Severity.HIGH, Severity.CRITICAL]


def test_anomaly_to_dict():
    """Test converting anomaly to dictionary."""
    anomaly = Anomaly(
        type=AnomalyType.THRESHOLD_BREACH,
        severity=Severity.HIGH,
        metric_name="svr",
        current_value=0.92,
        expected_value=0.95,
        deviation=3.16,
        timestamp=datetime.now(timezone.utc),
        agent="researcher",
        context={"threshold": 0.95}
    )

    data = anomaly.to_dict()

    assert data["type"] == "threshold_breach"
    assert data["severity"] == "high"
    assert data["metric_name"] == "svr"
    assert data["current_value"] == 0.92
    assert data["agent"] == "researcher"
