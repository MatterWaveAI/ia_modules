"""
Alert system for reliability monitoring.

Monitors metrics, anomalies, and SLO compliance, triggering alerts
when issues are detected. Supports multiple alert channels and
severity-based routing.
"""

from typing import Dict, Any, Optional, List, Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import Enum
import asyncio
import logging

from .anomaly_detection import Anomaly, Severity as AnomalySeverity
from .metrics import MetricsReport
from .slo_tracker import SLOReport


class AlertType(Enum):
    """Types of alerts that can be triggered."""
    METRIC_THRESHOLD = "metric_threshold"       # Metric exceeded threshold
    SLO_BREACH = "slo_breach"                   # SLO not met
    ANOMALY_DETECTED = "anomaly_detected"       # Anomaly detected
    TREND_WARNING = "trend_warning"             # Degrading trend detected
    HEALTH_CHECK_FAILED = "health_check_failed" # System health check failed
    COST_OVERRUN = "cost_overrun"              # Cost exceeded budget


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"           # Informational, no action needed
    WARNING = "warning"     # Warning, investigate when convenient
    ERROR = "error"         # Error, action required soon
    CRITICAL = "critical"   # Critical, immediate action required


@dataclass
class Alert:
    """
    Represents a triggered alert.

    Attributes:
        type: Type of alert
        severity: Severity level
        title: Short alert title
        message: Detailed alert message
        timestamp: When alert was triggered
        source: Source of alert (metric name, agent, etc.)
        context: Additional context information
        acknowledged: Whether alert has been acknowledged
        acknowledged_at: When alert was acknowledged
        acknowledged_by: Who acknowledged the alert
    """
    type: AlertType
    severity: AlertSeverity
    title: str
    message: str
    timestamp: datetime
    source: str
    context: Dict[str, Any] = field(default_factory=dict)
    acknowledged: bool = False
    acknowledged_at: Optional[datetime] = None
    acknowledged_by: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "type": self.type.value,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "timestamp": self.timestamp.isoformat(),
            "source": self.source,
            "context": self.context,
            "acknowledged": self.acknowledged,
            "acknowledged_at": self.acknowledged_at.isoformat() if self.acknowledged_at else None,
            "acknowledged_by": self.acknowledged_by
        }


class AlertChannel:
    """Base class for alert channels."""

    async def send_alert(self, alert: Alert):
        """Send alert through this channel."""
        raise NotImplementedError


class LogAlertChannel(AlertChannel):
    """Alert channel that logs to Python logging."""

    def __init__(self, logger: Optional[logging.Logger] = None):
        self.logger = logger or logging.getLogger("Alerts")

    async def send_alert(self, alert: Alert):
        """Log alert."""
        level_map = {
            AlertSeverity.INFO: logging.INFO,
            AlertSeverity.WARNING: logging.WARNING,
            AlertSeverity.ERROR: logging.ERROR,
            AlertSeverity.CRITICAL: logging.CRITICAL
        }

        level = level_map.get(alert.severity, logging.INFO)
        self.logger.log(level, f"[{alert.severity.value.upper()}] {alert.title}: {alert.message}")


class CallbackAlertChannel(AlertChannel):
    """Alert channel that calls a custom callback function."""

    def __init__(self, callback: Callable[[Alert], None]):
        self.callback = callback

    async def send_alert(self, alert: Alert):
        """Call callback with alert."""
        if asyncio.iscoroutinefunction(self.callback):
            await self.callback(alert)
        else:
            self.callback(alert)


@dataclass
class AlertRule:
    """
    Configuration for alert rule.

    Attributes:
        name: Rule name
        type: Alert type to generate
        severity: Alert severity
        enabled: Whether rule is enabled
        condition: Condition function that returns True to trigger alert
        title_template: Template for alert title (can use {metric_name}, etc.)
        message_template: Template for alert message
        cooldown_minutes: Minimum time between alerts for same condition
    """
    name: str
    type: AlertType
    severity: AlertSeverity
    enabled: bool = True
    condition: Optional[Callable[[Any], bool]] = None
    title_template: str = "{name} triggered"
    message_template: str = "Alert condition met"
    cooldown_minutes: int = 60


class AlertManager:
    """
    Manage alerts for reliability monitoring.

    Features:
    - Multiple alert channels (log, callback, webhook, etc.)
    - Alert rules with conditions and cooldowns
    - Alert deduplication and acknowledgment
    - Integration with anomaly detector, SLO tracker, metrics

    Example:
        >>> manager = AlertManager()
        >>>
        >>> # Add alert channel
        >>> manager.add_channel("log", LogAlertChannel())
        >>>
        >>> # Add alert rule for SLO breach
        >>> manager.add_rule(AlertRule(
        ...     name="slo_breach",
        ...     type=AlertType.SLO_BREACH,
        ...     severity=AlertSeverity.CRITICAL,
        ...     title_template="SLO Breach: {metric}",
        ...     message_template="SLO {metric} not met: {value} (target: {target})"
        ... ))
        >>>
        >>> # Trigger alert
        >>> await manager.trigger_slo_alert(slo_report, "mtte", compliant=False)
    """

    def __init__(self):
        """Initialize alert manager."""
        self.channels: Dict[str, AlertChannel] = {}
        self.rules: Dict[str, AlertRule] = {}
        self.alerts: List[Alert] = []

        # Track last alert time for cooldown
        self._last_alert_time: Dict[str, datetime] = {}

        # Track alert counts
        self._alert_counts: Dict[AlertType, int] = {}

        self.logger = logging.getLogger("AlertManager")

        # Add default log channel
        self.add_channel("log", LogAlertChannel())

    def add_channel(self, name: str, channel: AlertChannel):
        """
        Add alert channel.

        Args:
            name: Channel name
            channel: AlertChannel instance
        """
        self.channels[name] = channel
        self.logger.info(f"Added alert channel: {name}")

    def remove_channel(self, name: str) -> bool:
        """
        Remove alert channel.

        Args:
            name: Channel name

        Returns:
            True if removed, False if not found
        """
        if name in self.channels:
            del self.channels[name]
            self.logger.info(f"Removed alert channel: {name}")
            return True
        return False

    def add_rule(self, rule: AlertRule):
        """
        Add alert rule.

        Args:
            rule: AlertRule configuration
        """
        self.rules[rule.name] = rule
        self.logger.info(f"Added alert rule: {rule.name}")

    def remove_rule(self, name: str) -> bool:
        """
        Remove alert rule.

        Args:
            name: Rule name

        Returns:
            True if removed, False if not found
        """
        if name in self.rules:
            del self.rules[name]
            self.logger.info(f"Removed alert rule: {name}")
            return True
        return False

    def enable_rule(self, name: str) -> bool:
        """Enable alert rule."""
        if name in self.rules:
            self.rules[name].enabled = True
            return True
        return False

    def disable_rule(self, name: str) -> bool:
        """Disable alert rule."""
        if name in self.rules:
            self.rules[name].enabled = False
            return True
        return False

    async def trigger_alert(
        self,
        alert: Alert,
        channels: Optional[List[str]] = None
    ):
        """
        Trigger an alert.

        Args:
            alert: Alert to trigger
            channels: Specific channels to use (None = all)
        """
        # Check cooldown
        cooldown_key = f"{alert.type.value}:{alert.source}"
        if cooldown_key in self._last_alert_time:
            last_time = self._last_alert_time[cooldown_key]
            # Use default 60 minute cooldown
            if datetime.now(timezone.utc) - last_time < timedelta(minutes=60):
                self.logger.debug(f"Alert {cooldown_key} in cooldown, skipping")
                return

        # Store alert
        self.alerts.append(alert)

        # Update last alert time
        self._last_alert_time[cooldown_key] = datetime.now(timezone.utc)

        # Update alert counts
        if alert.type not in self._alert_counts:
            self._alert_counts[alert.type] = 0
        self._alert_counts[alert.type] += 1

        # Send to channels
        target_channels = channels or list(self.channels.keys())

        for channel_name in target_channels:
            if channel_name in self.channels:
                try:
                    await self.channels[channel_name].send_alert(alert)
                except Exception as e:
                    self.logger.error(f"Failed to send alert to {channel_name}: {e}")

        self.logger.info(f"Triggered alert: {alert.title} ({alert.severity.value})")

    async def trigger_metric_alert(
        self,
        metric_name: str,
        current_value: float,
        threshold: float,
        severity: AlertSeverity = AlertSeverity.WARNING
    ):
        """
        Trigger metric threshold alert.

        Args:
            metric_name: Metric name
            current_value: Current metric value
            threshold: Threshold value
            severity: Alert severity
        """
        alert = Alert(
            type=AlertType.METRIC_THRESHOLD,
            severity=severity,
            title=f"Metric Threshold Breach: {metric_name}",
            message=f"{metric_name} = {current_value:.4f} (threshold: {threshold:.4f})",
            timestamp=datetime.now(timezone.utc),
            source=metric_name,
            context={
                "metric_name": metric_name,
                "current_value": current_value,
                "threshold": threshold
            }
        )

        await self.trigger_alert(alert)

    async def trigger_slo_alert(
        self,
        slo_report: SLOReport,
        slo_name: str,
        compliant: bool
    ):
        """
        Trigger SLO compliance alert.

        Args:
            slo_report: SLO report
            slo_name: SLO name ("mtte" or "rsr")
            compliant: Whether SLO is compliant
        """
        if compliant:
            return  # Don't alert on compliance

        if slo_name == "mtte":
            value = slo_report.mtte_p95_ms
            target = slo_report.mtte_target_ms
        else:  # rsr
            value = slo_report.rsr
            target = slo_report.rsr_target

        alert = Alert(
            type=AlertType.SLO_BREACH,
            severity=AlertSeverity.CRITICAL,
            title=f"SLO Breach: {slo_name.upper()}",
            message=f"{slo_name.upper()} = {value} (target: {target})",
            timestamp=datetime.now(timezone.utc),
            source=slo_name,
            context={
                "slo_name": slo_name,
                "value": value,
                "target": target,
                "slo_report": slo_report.__dict__
            }
        )

        await self.trigger_alert(alert)

    async def trigger_anomaly_alert(self, anomaly: Anomaly):
        """
        Trigger anomaly detection alert.

        Args:
            anomaly: Detected anomaly
        """
        # Map anomaly severity to alert severity
        severity_map = {
            AnomalySeverity.LOW: AlertSeverity.INFO,
            AnomalySeverity.MEDIUM: AlertSeverity.WARNING,
            AnomalySeverity.HIGH: AlertSeverity.ERROR,
            AnomalySeverity.CRITICAL: AlertSeverity.CRITICAL
        }

        alert = Alert(
            type=AlertType.ANOMALY_DETECTED,
            severity=severity_map.get(anomaly.severity, AlertSeverity.WARNING),
            title=f"Anomaly Detected: {anomaly.metric_name}",
            message=f"{anomaly.type.value} in {anomaly.metric_name}: {anomaly.current_value:.4f} (expected: {anomaly.expected_value:.4f}, deviation: {anomaly.deviation:.2f})",
            timestamp=datetime.now(timezone.utc),
            source=anomaly.metric_name,
            context=anomaly.to_dict()
        )

        await self.trigger_alert(alert)

    async def trigger_health_check_alert(
        self,
        metrics_report: MetricsReport,
        failed_checks: List[str]
    ):
        """
        Trigger health check failure alert.

        Args:
            metrics_report: Metrics report
            failed_checks: List of failed health check names
        """
        alert = Alert(
            type=AlertType.HEALTH_CHECK_FAILED,
            severity=AlertSeverity.ERROR,
            title="Agent Health Check Failed",
            message=f"Failed checks: {', '.join(failed_checks)}",
            timestamp=datetime.now(timezone.utc),
            source="health_check",
            context={
                "failed_checks": failed_checks,
                "metrics": metrics_report.__dict__
            }
        )

        await self.trigger_alert(alert)

    def acknowledge_alert(
        self,
        alert_index: int,
        acknowledged_by: str
    ) -> bool:
        """
        Acknowledge an alert.

        Args:
            alert_index: Index of alert in alerts list
            acknowledged_by: Who acknowledged the alert

        Returns:
            True if acknowledged, False if not found
        """
        if 0 <= alert_index < len(self.alerts):
            alert = self.alerts[alert_index]
            alert.acknowledged = True
            alert.acknowledged_at = datetime.now(timezone.utc)
            alert.acknowledged_by = acknowledged_by
            self.logger.info(f"Alert acknowledged by {acknowledged_by}: {alert.title}")
            return True
        return False

    def get_alerts(
        self,
        since: Optional[datetime] = None,
        severity: Optional[AlertSeverity] = None,
        alert_type: Optional[AlertType] = None,
        acknowledged: Optional[bool] = None
    ) -> List[Alert]:
        """
        Retrieve alerts with filtering.

        Args:
            since: Only return alerts after this time
            severity: Filter by severity
            alert_type: Filter by alert type
            acknowledged: Filter by acknowledgment status

        Returns:
            Filtered list of alerts
        """
        filtered = self.alerts

        if since:
            filtered = [a for a in filtered if a.timestamp >= since]

        if severity:
            filtered = [a for a in filtered if a.severity == severity]

        if alert_type:
            filtered = [a for a in filtered if a.type == alert_type]

        if acknowledged is not None:
            filtered = [a for a in filtered if a.acknowledged == acknowledged]

        return filtered

    def get_alert_counts(self) -> Dict[str, int]:
        """
        Get counts of alerts by type.

        Returns:
            Dict mapping alert type to count
        """
        return {
            alert_type.value: count
            for alert_type, count in self._alert_counts.items()
        }

    def clear_alerts(self):
        """Clear all alerts."""
        self.alerts.clear()
        self.logger.info("Cleared all alerts")
