"""
Unit tests for telemetry metrics edge cases

Tests uncovered edge cases to reach 100% coverage.
"""

from ia_modules.telemetry.metrics import Metric, MetricType


class TestMetricEdgeCases:
    """Test edge cases in telemetry metrics"""

    def test_metric_with_labels_preserves_help_text(self):
        """Test that with_labels() preserves help_text"""
        metric = Metric(
            name="test_metric",
            metric_type=MetricType.COUNTER,
            value=42,
            labels={"env": "prod"},
            help_text="Test metric for counting things"
        )

        # Create new metric with additional labels
        new_metric = metric.with_labels(region="us-east-1")

        # Help text should be preserved
        assert new_metric.help_text == "Test metric for counting things"
        assert new_metric.labels["env"] == "prod"
        assert new_metric.labels["region"] == "us-east-1"

    def test_metric_with_labels_no_initial_labels(self):
        """Test with_labels() when metric has no initial labels"""
        metric = Metric(
            name="test_metric",
            metric_type=MetricType.GAUGE,
            value=100
        )

        # Add labels to metric with no initial labels
        new_metric = metric.with_labels(service="api", version="v1")

        assert new_metric.labels["service"] == "api"
        assert new_metric.labels["version"] == "v1"
        assert new_metric.name == "test_metric"
        assert new_metric.value == 100

    def test_metric_with_labels_overrides_existing(self):
        """Test that with_labels() overrides existing label values"""
        metric = Metric(
            name="test_metric",
            metric_type=MetricType.HISTOGRAM,
            value=50,
            labels={"env": "dev", "region": "us-west-1"}
        )

        # Override existing labels
        new_metric = metric.with_labels(env="prod")

        assert new_metric.labels["env"] == "prod"  # Overridden
        assert new_metric.labels["region"] == "us-west-1"  # Preserved


class TestMetricsCollectorEdgeCases:
    """Test edge cases in MetricsCollector"""

    def test_remove_nonexistent_metric(self):
        """Test removing a metric that doesn't exist"""
        from ia_modules.telemetry.metrics import MetricsCollector

        collector = MetricsCollector()

        # Try to remove metric that was never added
        result = collector.remove_metric("nonexistent_metric")

        assert result is False

    def test_get_nonexistent_metric(self):
        """Test getting a metric that doesn't exist"""
        from ia_modules.telemetry.metrics import MetricsCollector

        collector = MetricsCollector()

        # Try to get metric that was never added
        result = collector.get_metric("nonexistent_metric")

        assert result is None

    def test_clear_metrics(self):
        """Test clearing all metrics"""
        from ia_modules.telemetry.metrics import MetricsCollector

        collector = MetricsCollector()

        # Add some metrics
        collector.counter("requests_total")
        collector.gauge("active_connections")
        collector.histogram("request_duration")

        # Clear all metrics
        collector.clear()

        # Verify all metrics are removed
        assert collector.get_metric("requests_total") is None
        assert collector.get_metric("active_connections") is None
        assert collector.get_metric("request_duration") is None
        assert len(collector.collect_all()) == 0


class TestSummaryQuantileEdgeCases:
    """Test edge cases in Summary quantile calculation"""

    def test_summary_quantile_with_empty_observations(self):
        """Test that quantile calculation handles empty observations"""
        from ia_modules.telemetry.metrics import Summary

        summary = Summary("response_time", quantiles=[0.5, 0.95, 0.99])

        # Collect without any observations
        metrics = summary.collect()

        # Should return empty list when no observations
        assert len(metrics) == 0

    def test_summary_quantile_boundary_conditions(self):
        """Test quantile calculation at boundaries"""
        from ia_modules.telemetry.metrics import Summary

        summary = Summary("response_time", quantiles=[0.5, 0.95, 0.99])

        # Add observations
        for value in [1.0, 2.0, 3.0, 4.0, 5.0]:
            summary.observe(value)

        metrics = summary.collect()
        assert len(metrics) == 1

        metric = metrics[0]
        assert metric.value['count'] == 5
        assert metric.value['sum'] == 15.0

        # Verify quantiles are calculated
        quantiles = metric.value['quantiles']
        assert 0.5 in quantiles  # Median should exist
        assert 0.95 in quantiles
        assert 0.99 in quantiles
