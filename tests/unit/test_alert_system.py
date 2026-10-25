"""Tests for alert system."""

import pytest
from datetime import datetime, timedelta, timezone

from ia_modules.reliability.alert_system import (
    AlertManager,
    Alert,
    AlertType,
    AlertSeverity,
    AlertRule,
    LogAlertChannel,
    CallbackAlertChannel
)
from ia_modules.reliability.anomaly_detection import Anomaly, AnomalyType, Severity as AnomalySeverity
from ia_modules.reliability.metrics import MetricsReport
from ia_modules.reliability.slo_tracker import SLOReport


@pytest.mark.asyncio
async def test_alert_manager_creation():
    """Test creating alert manager."""
    manager = AlertManager()

    assert len(manager.channels) == 1  # Default log channel
    assert "log" in manager.channels
    assert len(manager.rules) == 0


@pytest.mark.asyncio
async def test_add_channel():
    """Test adding alert channel."""
    manager = AlertManager()

    channel = LogAlertChannel()
    manager.add_channel("test", channel)

    assert "test" in manager.channels
    assert manager.channels["test"] == channel


@pytest.mark.asyncio
async def test_remove_channel():
    """Test removing alert channel."""
    manager = AlertManager()

    channel = LogAlertChannel()
    manager.add_channel("test", channel)

    result = manager.remove_channel("test")
    assert result is True
    assert "test" not in manager.channels

    # Try removing non-existent channel
    result = manager.remove_channel("nonexistent")
    assert result is False


@pytest.mark.asyncio
async def test_add_rule():
    """Test adding alert rule."""
    manager = AlertManager()

    rule = AlertRule(
        name="test_rule",
        type=AlertType.METRIC_THRESHOLD,
        severity=AlertSeverity.WARNING
    )

    manager.add_rule(rule)

    assert "test_rule" in manager.rules
    assert manager.rules["test_rule"] == rule


@pytest.mark.asyncio
async def test_remove_rule():
    """Test removing alert rule."""
    manager = AlertManager()

    rule = AlertRule(
        name="test_rule",
        type=AlertType.METRIC_THRESHOLD,
        severity=AlertSeverity.WARNING
    )
    manager.add_rule(rule)

    result = manager.remove_rule("test_rule")
    assert result is True
    assert "test_rule" not in manager.rules


@pytest.mark.asyncio
async def test_enable_disable_rule():
    """Test enabling and disabling alert rules."""
    manager = AlertManager()

    rule = AlertRule(
        name="test_rule",
        type=AlertType.METRIC_THRESHOLD,
        severity=AlertSeverity.WARNING,
        enabled=True
    )
    manager.add_rule(rule)

    # Disable
    result = manager.disable_rule("test_rule")
    assert result is True
    assert manager.rules["test_rule"].enabled is False

    # Enable
    result = manager.enable_rule("test_rule")
    assert result is True
    assert manager.rules["test_rule"].enabled is True


@pytest.mark.asyncio
async def test_trigger_alert():
    """Test triggering an alert."""
    manager = AlertManager()

    # Track alerts via callback
    triggered_alerts = []

    def callback(alert: Alert):
        triggered_alerts.append(alert)

    manager.add_channel("callback", CallbackAlertChannel(callback))

    alert = Alert(
        type=AlertType.METRIC_THRESHOLD,
        severity=AlertSeverity.WARNING,
        title="Test Alert",
        message="This is a test",
        timestamp=datetime.now(timezone.utc),
        source="test"
    )

    await manager.trigger_alert(alert)

    # Alert should be stored
    assert len(manager.alerts) == 1
    assert manager.alerts[0] == alert

    # Callback should have been called
    assert len(triggered_alerts) == 1
    assert triggered_alerts[0] == alert


@pytest.mark.asyncio
async def test_trigger_metric_alert():
    """Test triggering metric threshold alert."""
    manager = AlertManager()

    await manager.trigger_metric_alert(
        metric_name="svr",
        current_value=0.92,
        threshold=0.95,
        severity=AlertSeverity.WARNING
    )

    assert len(manager.alerts) == 1
    alert = manager.alerts[0]

    assert alert.type == AlertType.METRIC_THRESHOLD
    assert alert.severity == AlertSeverity.WARNING
    assert alert.source == "svr"
    assert alert.context["current_value"] == 0.92
    assert alert.context["threshold"] == 0.95


@pytest.mark.asyncio
async def test_trigger_slo_alert():
    """Test triggering SLO breach alert."""
    manager = AlertManager()

    slo_report = SLOReport(
        period_start=datetime.now(timezone.utc) - timedelta(hours=24),
        period_end=datetime.now(timezone.utc),
        mtte_avg_ms=350000,
        mtte_p50_ms=300000,
        mtte_p95_ms=400000,  # Exceeds 5 min target
        mtte_p99_ms=450000,
        mtte_target_ms=300000,
        rsr=0.95,
        rsr_target=0.99,
        total_mtte_measurements=100,
        total_rsr_attempts=100,
        successful_replays=95
    )

    await manager.trigger_slo_alert(slo_report, "mtte", compliant=False)

    assert len(manager.alerts) == 1
    alert = manager.alerts[0]

    assert alert.type == AlertType.SLO_BREACH
    assert alert.severity == AlertSeverity.CRITICAL
    assert alert.source == "mtte"


@pytest.mark.asyncio
async def test_trigger_anomaly_alert():
    """Test triggering anomaly detection alert."""
    manager = AlertManager()

    anomaly = Anomaly(
        type=AnomalyType.SUDDEN_SPIKE,
        severity=AnomalySeverity.HIGH,
        metric_name="latency",
        current_value=500.0,
        expected_value=100.0,
        deviation=4.5,
        timestamp=datetime.now(timezone.utc),
        agent="researcher"
    )

    await manager.trigger_anomaly_alert(anomaly)

    assert len(manager.alerts) == 1
    alert = manager.alerts[0]

    assert alert.type == AlertType.ANOMALY_DETECTED
    assert alert.severity == AlertSeverity.ERROR  # HIGH anomaly -> ERROR alert
    assert alert.source == "latency"


@pytest.mark.asyncio
async def test_trigger_health_check_alert():
    """Test triggering health check failure alert."""
    manager = AlertManager()

    metrics_report = MetricsReport(
        period_start=datetime.now(timezone.utc) - timedelta(hours=24),
        period_end=datetime.now(timezone.utc),
        total_workflows=10,
        total_steps=100,
        svr=0.92,  # Below target
        cr=0.05,
        pc=1.5,
        hir=0.03,
        ma=0.98,
        agent_metrics={}
    )

    await manager.trigger_health_check_alert(
        metrics_report,
        failed_checks=["svr"]
    )

    assert len(manager.alerts) == 1
    alert = manager.alerts[0]

    assert alert.type == AlertType.HEALTH_CHECK_FAILED
    assert alert.severity == AlertSeverity.ERROR
    assert "svr" in alert.context["failed_checks"]


@pytest.mark.asyncio
async def test_alert_cooldown():
    """Test alert cooldown prevents duplicate alerts."""
    manager = AlertManager()

    # Trigger first alert
    await manager.trigger_metric_alert(
        metric_name="svr",
        current_value=0.92,
        threshold=0.95
    )

    assert len(manager.alerts) == 1

    # Trigger same alert immediately (should be suppressed)
    await manager.trigger_metric_alert(
        metric_name="svr",
        current_value=0.92,
        threshold=0.95
    )

    # Should still only have 1 alert due to cooldown
    assert len(manager.alerts) == 1


@pytest.mark.asyncio
async def test_acknowledge_alert():
    """Test acknowledging an alert."""
    manager = AlertManager()

    await manager.trigger_metric_alert(
        metric_name="svr",
        current_value=0.92,
        threshold=0.95
    )

    # Acknowledge the alert
    result = manager.acknowledge_alert(0, "admin")

    assert result is True
    assert manager.alerts[0].acknowledged is True
    assert manager.alerts[0].acknowledged_by == "admin"
    assert manager.alerts[0].acknowledged_at is not None


@pytest.mark.asyncio
async def test_get_alerts_filtering():
    """Test retrieving alerts with filters."""
    manager = AlertManager()

    # Trigger different types of alerts
    await manager.trigger_metric_alert(
        metric_name="svr",
        current_value=0.92,
        threshold=0.95,
        severity=AlertSeverity.WARNING
    )

    await manager.trigger_metric_alert(
        metric_name="cr",
        current_value=0.15,
        threshold=0.10,
        severity=AlertSeverity.ERROR
    )

    # Filter by severity
    warnings = manager.get_alerts(severity=AlertSeverity.WARNING)
    assert len(warnings) == 1
    assert warnings[0].source == "svr"

    errors = manager.get_alerts(severity=AlertSeverity.ERROR)
    assert len(errors) == 1
    assert errors[0].source == "cr"

    # Filter by type
    metric_alerts = manager.get_alerts(alert_type=AlertType.METRIC_THRESHOLD)
    assert len(metric_alerts) == 2

    # Filter by acknowledgment
    manager.acknowledge_alert(0, "admin")
    acknowledged = manager.get_alerts(acknowledged=True)
    assert len(acknowledged) == 1

    unacknowledged = manager.get_alerts(acknowledged=False)
    assert len(unacknowledged) == 1


@pytest.mark.asyncio
async def test_get_alerts_time_filter():
    """Test retrieving alerts with time filter."""
    manager = AlertManager()

    # Trigger alert in the past
    past_alert = Alert(
        type=AlertType.METRIC_THRESHOLD,
        severity=AlertSeverity.WARNING,
        title="Past Alert",
        message="Old alert",
        timestamp=datetime.now(timezone.utc) - timedelta(hours=2),
        source="test"
    )
    await manager.trigger_alert(past_alert)

    # Trigger recent alert
    await manager.trigger_metric_alert(
        metric_name="svr",
        current_value=0.92,
        threshold=0.95
    )

    # Filter by time
    since = datetime.now(timezone.utc) - timedelta(hours=1)
    recent = manager.get_alerts(since=since)

    assert len(recent) == 1
    assert recent[0].source == "svr"


@pytest.mark.asyncio
async def test_get_alert_counts():
    """Test getting alert counts by type."""
    manager = AlertManager()

    # Trigger multiple alerts
    await manager.trigger_metric_alert("svr", 0.92, 0.95)
    await manager.trigger_metric_alert("cr", 0.15, 0.10)

    anomaly = Anomaly(
        type=AnomalyType.SUDDEN_SPIKE,
        severity=AnomalySeverity.HIGH,
        metric_name="latency",
        current_value=500.0,
        expected_value=100.0,
        deviation=4.5,
        timestamp=datetime.now(timezone.utc)
    )
    await manager.trigger_anomaly_alert(anomaly)

    counts = manager.get_alert_counts()

    assert counts["metric_threshold"] == 2
    assert counts["anomaly_detected"] == 1


@pytest.mark.asyncio
async def test_clear_alerts():
    """Test clearing all alerts."""
    manager = AlertManager()

    # Trigger some alerts
    await manager.trigger_metric_alert("svr", 0.92, 0.95)
    await manager.trigger_metric_alert("cr", 0.15, 0.10)

    assert len(manager.alerts) > 0

    manager.clear_alerts()

    assert len(manager.alerts) == 0


@pytest.mark.asyncio
async def test_callback_alert_channel_async():
    """Test callback channel with async callback."""
    triggered = []

    async def async_callback(alert: Alert):
        triggered.append(alert)

    channel = CallbackAlertChannel(async_callback)

    alert = Alert(
        type=AlertType.METRIC_THRESHOLD,
        severity=AlertSeverity.WARNING,
        title="Test",
        message="Test",
        timestamp=datetime.now(timezone.utc),
        source="test"
    )

    await channel.send_alert(alert)

    assert len(triggered) == 1
    assert triggered[0] == alert


@pytest.mark.asyncio
async def test_alert_to_dict():
    """Test converting alert to dictionary."""
    alert = Alert(
        type=AlertType.METRIC_THRESHOLD,
        severity=AlertSeverity.WARNING,
        title="Test Alert",
        message="Test message",
        timestamp=datetime.now(timezone.utc),
        source="test_metric",
        context={"value": 0.92}
    )

    data = alert.to_dict()

    assert data["type"] == "metric_threshold"
    assert data["severity"] == "warning"
    assert data["title"] == "Test Alert"
    assert data["message"] == "Test message"
    assert data["source"] == "test_metric"
    assert data["context"]["value"] == 0.92
    assert data["acknowledged"] is False
