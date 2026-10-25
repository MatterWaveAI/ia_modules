"""
Tests for telemetry exporters
"""

from ia_modules.telemetry import (
    MetricsCollector,
    PrometheusExporter,
    StatsDExporter,
    Metric,
    MetricType
)


class TestPrometheusExporter:
    """Test Prometheus exporter"""

    def test_exporter_creation(self):
        """Test creating Prometheus exporter"""
        exporter = PrometheusExporter(prefix="test_app", port=9090)
        assert exporter.prefix == "test_app"
        assert exporter.port == 9090

    def test_export_counter(self):
        """Test exporting counter metrics"""
        collector = MetricsCollector()
        counter = collector.counter("requests_total", help_text="Total requests", labels=["method"])

        counter.inc(method="GET")
        counter.inc(method="POST")

        exporter = PrometheusExporter(prefix="app")
        exporter.export(collector.collect_all())

        text = exporter.get_metrics_text()
        assert "# HELP app_requests_total Total requests" in text
        assert "# TYPE app_requests_total counter" in text
        assert 'app_requests_total{method="GET"} 1.0' in text
        assert 'app_requests_total{method="POST"} 1.0' in text

    def test_export_gauge(self):
        """Test exporting gauge metrics"""
        collector = MetricsCollector()
        gauge = collector.gauge("temperature", help_text="Current temperature")

        gauge.set(25.5)

        exporter = PrometheusExporter(prefix="sensor")
        exporter.export(collector.collect_all())

        text = exporter.get_metrics_text()
        assert "# HELP sensor_temperature Current temperature" in text
        assert "# TYPE sensor_temperature gauge" in text
        assert "sensor_temperature 25.5" in text

    def test_export_histogram(self):
        """Test exporting histogram metrics"""
        collector = MetricsCollector()
        histogram = collector.histogram(
            "request_duration_seconds",
            help_text="Request duration",
            buckets=[0.1, 0.5, 1.0]
        )

        histogram.observe(0.05)
        histogram.observe(0.3)
        histogram.observe(0.8)

        exporter = PrometheusExporter(prefix="http")
        exporter.export(collector.collect_all())

        text = exporter.get_metrics_text()
        assert "# HELP http_request_duration_seconds Request duration" in text
        assert "# TYPE http_request_duration_seconds histogram" in text
        assert "_bucket" in text
        assert "_sum" in text
        assert "_count" in text

    def test_export_summary(self):
        """Test exporting summary metrics"""
        collector = MetricsCollector()
        summary = collector.summary(
            "latency_seconds",
            help_text="Latency",
            quantiles=[0.5, 0.9, 0.99]
        )

        for i in range(100):
            summary.observe(i * 0.01)

        exporter = PrometheusExporter(prefix="api")
        exporter.export(collector.collect_all())

        text = exporter.get_metrics_text()
        assert "# HELP api_latency_seconds Latency" in text
        assert "# TYPE api_latency_seconds summary" in text
        assert "quantile" in text
        assert "_sum" in text
        assert "_count" in text

    def test_no_prefix(self):
        """Test exporter without prefix"""
        collector = MetricsCollector()
        counter = collector.counter("my_metric")
        counter.inc()

        exporter = PrometheusExporter(prefix="")
        exporter.export(collector.collect_all())

        text = exporter.get_metrics_text()
        assert "my_metric 1.0" in text


class TestStatsDExporter:
    """Test StatsD exporter"""

    def test_exporter_creation(self):
        """Test creating StatsD exporter"""
        exporter = StatsDExporter(host="localhost", port=8125, prefix="test")
        assert exporter.host == "localhost"
        assert exporter.port == 8125
        assert exporter.prefix == "test"

    def test_format_counter(self):
        """Test formatting counter for StatsD"""
        exporter = StatsDExporter(prefix="app")

        metric = Metric(
            name="requests",
            metric_type=MetricType.COUNTER,
            value=5.0,
            labels={"method": "GET"}
        )

        formatted = exporter._format_statsd_metric(metric)
        assert formatted == "app_requests,method:GET:5.0|c"

    def test_format_gauge(self):
        """Test formatting gauge for StatsD"""
        exporter = StatsDExporter(prefix="sensor")

        metric = Metric(
            name="temperature",
            metric_type=MetricType.GAUGE,
            value=25.5
        )

        formatted = exporter._format_statsd_metric(metric)
        assert formatted == "sensor_temperature:25.5|g"

    def test_format_histogram(self):
        """Test formatting histogram for StatsD"""
        exporter = StatsDExporter(prefix="http")

        metric = Metric(
            name="duration",
            metric_type=MetricType.HISTOGRAM,
            value={'sum': 1.25, 'count': 5}
        )

        formatted = exporter._format_statsd_metric(metric)
        assert formatted == "http_duration:1.25|ms"


class TestExporterIntegration:
    """Test exporters with real metrics"""

    def test_multiple_exporters(self):
        """Test using multiple exporters"""
        collector = MetricsCollector()

        # Create metrics
        requests = collector.counter("requests", labels=["status"])
        requests.inc(status="200")
        requests.inc(status="404")

        latency = collector.gauge("latency_ms")
        latency.set(125.5)

        # Export to both
        prom_exporter = PrometheusExporter(prefix="app")
        statsd_exporter = StatsDExporter(prefix="app")

        metrics = collector.collect_all()

        prom_exporter.export(metrics)
        statsd_exporter.export(metrics)

        # Verify Prometheus
        prom_text = prom_exporter.get_metrics_text()
        assert "app_requests" in prom_text
        assert "app_latency_ms" in prom_text

    def test_real_world_scenario(self):
        """Test real-world metrics collection and export"""
        collector = MetricsCollector()

        # API metrics
        http_requests = collector.counter(
            "http_requests_total",
            help_text="Total HTTP requests",
            labels=["method", "endpoint", "status"]
        )

        http_duration = collector.histogram(
            "http_request_duration_seconds",
            help_text="HTTP request duration",
            labels=["endpoint"],
            buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0]
        )

        active_connections = collector.gauge(
            "active_connections",
            help_text="Active connections"
        )

        # Simulate traffic
        http_requests.inc(method="GET", endpoint="/users", status="200")
        http_requests.inc(method="GET", endpoint="/users", status="200")
        http_requests.inc(method="POST", endpoint="/users", status="201")
        http_requests.inc(method="GET", endpoint="/posts", status="404")

        http_duration.observe(0.05, endpoint="/users")
        http_duration.observe(0.12, endpoint="/users")
        http_duration.observe(0.03, endpoint="/posts")

        active_connections.set(42)

        # Export
        exporter = PrometheusExporter(prefix="myapp")
        exporter.export(collector.collect_all())

        text = exporter.get_metrics_text()

        # Verify all metrics present
        assert "myapp_http_requests_total" in text
        assert "myapp_http_request_duration_seconds" in text
        assert "myapp_active_connections" in text

        # Verify labels
        assert 'method="GET"' in text
        assert 'endpoint="/users"' in text
        assert 'status="200"' in text


class TestExporterEdgeCases:
    """Test edge cases for exporters"""

    def test_empty_metrics(self):
        """Test exporting empty metrics"""
        exporter = PrometheusExporter()
        exporter.export([])

        text = exporter.get_metrics_text()
        assert text == "\n"

    def test_special_characters_in_labels(self):
        """Test labels with special characters"""
        collector = MetricsCollector()
        counter = collector.counter("requests", labels=["path"])

        counter.inc(path="/api/v1/users?page=1&sort=desc")

        exporter = PrometheusExporter()
        exporter.export(collector.collect_all())

        text = exporter.get_metrics_text()
        assert "requests" in text
        # Should handle special characters

    def test_large_number_of_metrics(self):
        """Test exporting large number of metrics"""
        collector = MetricsCollector()

        # Create 100 different counters
        for i in range(100):
            counter = collector.counter(f"metric_{i}")
            counter.inc()

        exporter = PrometheusExporter()
        metrics = collector.collect_all()

        assert len(metrics) == 100

        exporter.export(metrics)
        text = exporter.get_metrics_text()

        # Should have all metrics
        assert text.count("# TYPE") == 100
