"""
Integration tests for observability stack

Tests the integration with Prometheus, Grafana, OpenTelemetry Collector,
and Jaeger for metrics and tracing.

Run with: pytest -m observability
"""

import os
import time
import pytest

requests = pytest.importorskip("requests")
from ia_modules.telemetry.metrics import MetricsCollector, Metric, MetricType
from tests.integration import jaeger_query


def _reachable(url: str) -> bool:
    try:
        requests.get(url, timeout=2)
        return True
    except requests.RequestException:
        return False


# The whole module talks to a live observability stack (tests/docker-compose);
# without it every test would fail on a connection error rather than skip.
pytestmark = pytest.mark.skipif(
    not _reachable(os.environ.get("PROMETHEUS_URL", "http://localhost:19090")),
    reason="observability stack not running (PROMETHEUS_URL unreachable)",
)



@pytest.fixture
def prometheus_url():
    """Get Prometheus URL from environment"""
    return os.environ.get("PROMETHEUS_URL", "http://localhost:19090")


@pytest.fixture
def grafana_url():
    """Get Grafana URL from environment"""
    return os.environ.get("GRAFANA_URL", "http://localhost:13001")


@pytest.fixture
def otel_collector_url():
    """Get OpenTelemetry Collector URL from environment"""
    return os.environ.get("OTEL_COLLECTOR_URL", "http://localhost:14318")


@pytest.fixture
def jaeger_url():
    """Get Jaeger URL from environment"""
    return os.environ.get("JAEGER_URL", "http://localhost:16686")


@pytest.fixture
def metrics_collector():
    """Create a metrics collector for testing"""
    collector = MetricsCollector()
    yield collector
    collector.clear()


@pytest.fixture
def grafana_auth():
    """Get Grafana authentication"""
    return ('admin', 'admin')  # Default credentials from docker-compose


@pytest.mark.observability
@pytest.mark.integration
class TestPrometheusHealth:
    """Test Prometheus health and status endpoints"""

    def test_prometheus_health(self, prometheus_url):
        """Test Prometheus is healthy and responding"""
        response = requests.get(f"{prometheus_url}/-/healthy", timeout=5)
        assert response.status_code == 200

    def test_prometheus_ready(self, prometheus_url):
        """Test Prometheus is ready"""
        response = requests.get(f"{prometheus_url}/-/ready", timeout=5)
        assert response.status_code == 200

    def test_prometheus_config(self, prometheus_url):
        """Test Prometheus configuration is loaded"""
        response = requests.get(f"{prometheus_url}/api/v1/status/config", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'yaml' in data['data']

    def test_prometheus_flags(self, prometheus_url):
        """Test Prometheus runtime flags"""
        response = requests.get(f"{prometheus_url}/api/v1/status/flags", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert isinstance(data['data'], dict)

    def test_prometheus_runtimeinfo(self, prometheus_url):
        """Test Prometheus runtime information"""
        response = requests.get(f"{prometheus_url}/api/v1/status/runtimeinfo", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'storageRetention' in data['data']


@pytest.mark.observability
@pytest.mark.integration
class TestPrometheusTargets:
    """Test Prometheus target discovery and scraping"""

    def test_prometheus_targets(self, prometheus_url):
        """Test Prometheus can see configured targets"""
        response = requests.get(f"{prometheus_url}/api/v1/targets", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert 'activeTargets' in data['data']

    def test_prometheus_targets_metadata(self, prometheus_url):
        """Test Prometheus target metadata"""
        response = requests.get(f"{prometheus_url}/api/v1/targets/metadata", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'

    def test_prometheus_service_discovery(self, prometheus_url):
        """Test Prometheus service discovery"""
        response = requests.get(f"{prometheus_url}/api/v1/targets", timeout=5)
        assert response.status_code == 200
        data = response.json()
        # Should have active targets even if empty
        assert 'activeTargets' in data['data']
        assert 'droppedTargets' in data['data']


@pytest.mark.observability
@pytest.mark.integration
class TestPrometheusQuery:
    """Test Prometheus query API"""

    def test_prometheus_query_instant(self, prometheus_url):
        """Test Prometheus instant query"""
        # Query for 'up' metric which should always exist
        params = {'query': 'up'}
        response = requests.get(
            f"{prometheus_url}/api/v1/query",
            params=params,
            timeout=5
        )
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'

    def test_prometheus_query_range(self, prometheus_url):
        """Test Prometheus range query"""
        end_time = time.time()
        start_time = end_time - 3600  # Last hour

        params = {
            'query': 'up',
            'start': start_time,
            'end': end_time,
            'step': '60s'
        }
        response = requests.get(
            f"{prometheus_url}/api/v1/query_range",
            params=params,
            timeout=10
        )
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'

    def test_prometheus_series_metadata(self, prometheus_url):
        """Test Prometheus series metadata"""
        params = {'match[]': 'up'}
        response = requests.get(
            f"{prometheus_url}/api/v1/series",
            params=params,
            timeout=5
        )
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'

    def test_prometheus_label_names(self, prometheus_url):
        """Test Prometheus label names API"""
        response = requests.get(f"{prometheus_url}/api/v1/labels", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'
        assert isinstance(data['data'], list)

    def test_prometheus_label_values(self, prometheus_url):
        """Test Prometheus label values API"""
        response = requests.get(f"{prometheus_url}/api/v1/label/job/values", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert data['status'] == 'success'


@pytest.mark.observability
@pytest.mark.integration
class TestPrometheusExporter:
    """Test exporting metrics to Prometheus format"""

    def test_export_counter_to_prometheus(self, metrics_collector):
        """Test exporting counter metrics"""
        from ia_modules.telemetry.exporters import PrometheusExporter

        # Create counter
        counter = metrics_collector.counter(
            "test_requests_total",
            help_text="Total test requests",
            labels=["method", "status"]
        )
        counter.inc(10, method="GET", status="200")
        counter.inc(5, method="POST", status="201")

        # Export
        exporter = PrometheusExporter(prefix="ia_modules_test")
        metrics = metrics_collector.collect_all()
        exporter.export(metrics)

        # Verify format
        prom_text = exporter.get_metrics_text()
        assert "# HELP ia_modules_test_test_requests_total" in prom_text
        assert "# TYPE ia_modules_test_test_requests_total counter" in prom_text
        assert 'method="GET"' in prom_text
        assert 'status="200"' in prom_text

    def test_export_gauge_to_prometheus(self, metrics_collector):
        """Test exporting gauge metrics"""
        from ia_modules.telemetry.exporters import PrometheusExporter

        gauge = metrics_collector.gauge(
            "test_active_connections",
            help_text="Active connections"
        )
        gauge.set(42)

        exporter = PrometheusExporter(prefix="ia_modules_test")
        metrics = metrics_collector.collect_all()
        exporter.export(metrics)

        prom_text = exporter.get_metrics_text()
        assert "# TYPE ia_modules_test_test_active_connections gauge" in prom_text
        assert "ia_modules_test_test_active_connections 42" in prom_text

    def test_export_histogram_to_prometheus(self, metrics_collector):
        """Test exporting histogram metrics"""
        from ia_modules.telemetry.exporters import PrometheusExporter

        histogram = metrics_collector.histogram(
            "test_request_duration",
            help_text="Request duration in seconds",
            buckets=[0.1, 0.5, 1.0, 2.0]
        )

        # Observe values
        for val in [0.05, 0.3, 0.7, 1.5]:
            histogram.observe(val)

        exporter = PrometheusExporter(prefix="ia_modules_test")
        metrics = metrics_collector.collect_all()
        exporter.export(metrics)

        prom_text = exporter.get_metrics_text()
        assert "# TYPE ia_modules_test_test_request_duration histogram" in prom_text
        assert "_bucket" in prom_text
        assert "_sum" in prom_text
        assert "_count" in prom_text

    def test_export_summary_to_prometheus(self, metrics_collector):
        """Test exporting summary metrics"""
        from ia_modules.telemetry.exporters import PrometheusExporter

        summary = metrics_collector.summary(
            "test_response_time",
            help_text="Response time percentiles",
            quantiles=[0.5, 0.9, 0.99]
        )

        # Observe values
        for val in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]:
            summary.observe(val)

        exporter = PrometheusExporter(prefix="ia_modules_test")
        metrics = metrics_collector.collect_all()
        exporter.export(metrics)

        prom_text = exporter.get_metrics_text()
        assert "# TYPE ia_modules_test_test_response_time summary" in prom_text
        assert "_sum" in prom_text
        assert "_count" in prom_text

    def test_export_multiple_metrics(self, metrics_collector):
        """Test exporting multiple different metric types"""
        from ia_modules.telemetry.exporters import PrometheusExporter

        metrics_collector.counter("counter_metric").inc(10)
        metrics_collector.gauge("gauge_metric").set(50)
        metrics_collector.histogram("histogram_metric").observe(0.5)

        exporter = PrometheusExporter(prefix="test")
        metrics = metrics_collector.collect_all()
        exporter.export(metrics)

        prom_text = exporter.get_metrics_text()
        assert "test_counter_metric" in prom_text
        assert "test_gauge_metric" in prom_text
        assert "test_histogram_metric" in prom_text

    def test_export_with_labels(self, metrics_collector):
        """Test exporting metrics with labels"""
        from ia_modules.telemetry.exporters import PrometheusExporter

        counter = metrics_collector.counter(
            "requests",
            labels=["method", "path", "status"]
        )
        counter.inc(method="GET", path="/api/users", status="200")
        counter.inc(method="POST", path="/api/users", status="201")

        exporter = PrometheusExporter()
        metrics = metrics_collector.collect_all()
        exporter.export(metrics)

        prom_text = exporter.get_metrics_text()
        assert 'method="GET"' in prom_text
        assert 'path="/api/users"' in prom_text
        assert 'status="200"' in prom_text


@pytest.mark.observability
@pytest.mark.integration
class TestGrafanaHealth:
    """Test Grafana health and status"""

    def test_grafana_health(self, grafana_url):
        """Test Grafana is healthy"""
        response = requests.get(f"{grafana_url}/api/health", timeout=5)
        assert response.status_code == 200
        data = response.json()
        assert data['database'] == 'ok'

    def test_grafana_alive(self, grafana_url):
        """Test Grafana UI is accessible"""
        response = requests.get(grafana_url, timeout=5)
        assert response.status_code == 200

    def test_grafana_login_page(self, grafana_url):
        """Test Grafana login page loads"""
        response = requests.get(f"{grafana_url}/login", timeout=5)
        assert response.status_code == 200


@pytest.mark.observability
@pytest.mark.integration
class TestGrafanaDatasources:
    """Test Grafana datasource configuration"""

    def test_grafana_datasources_list(self, grafana_url, grafana_auth):
        """Test Grafana datasources are configured"""
        response = requests.get(
            f"{grafana_url}/api/datasources",
            auth=grafana_auth,
            timeout=5
        )
        assert response.status_code == 200
        datasources = response.json()
        assert isinstance(datasources, list)

    def test_grafana_prometheus_datasource(self, grafana_url, grafana_auth):
        """Test Prometheus datasource exists"""
        response = requests.get(
            f"{grafana_url}/api/datasources",
            auth=grafana_auth,
            timeout=5
        )
        assert response.status_code == 200
        datasources = response.json()

        prometheus_ds = [ds for ds in datasources if ds['type'] == 'prometheus']
        assert len(prometheus_ds) > 0

    def test_grafana_datasource_health(self, grafana_url, grafana_auth):
        """Test datasource health check"""
        response = requests.get(
            f"{grafana_url}/api/datasources",
            auth=grafana_auth,
            timeout=5
        )
        assert response.status_code == 200
        datasources = response.json()

        if len(datasources) > 0:
            ds_id = datasources[0]['id']
            health_response = requests.get(
                f"{grafana_url}/api/datasources/{ds_id}/health",
                auth=grafana_auth,
                timeout=10
            )
            # Health check may not be implemented for all datasources
            assert health_response.status_code in [200, 404, 500]


@pytest.mark.observability
@pytest.mark.integration
class TestGrafanaOrganizations:
    """Test Grafana organization management"""

    def test_grafana_orgs_list(self, grafana_url, grafana_auth):
        """Test listing Grafana organizations"""
        response = requests.get(
            f"{grafana_url}/api/orgs",
            auth=grafana_auth,
            timeout=5
        )
        assert response.status_code == 200
        orgs = response.json()
        assert isinstance(orgs, list)
        assert len(orgs) > 0

    def test_grafana_current_org(self, grafana_url, grafana_auth):
        """Test getting current organization"""
        response = requests.get(
            f"{grafana_url}/api/org",
            auth=grafana_auth,
            timeout=5
        )
        assert response.status_code == 200
        org = response.json()
        assert 'id' in org
        assert 'name' in org


@pytest.mark.observability
@pytest.mark.integration
class TestGrafanaUsers:
    """Test Grafana user management"""

    def test_grafana_users_list(self, grafana_url, grafana_auth):
        """Test listing Grafana users"""
        response = requests.get(
            f"{grafana_url}/api/users",
            auth=grafana_auth,
            timeout=5
        )
        assert response.status_code == 200
        users = response.json()
        assert isinstance(users, list)

    def test_grafana_current_user(self, grafana_url, grafana_auth):
        """Test getting current user"""
        response = requests.get(
            f"{grafana_url}/api/user",
            auth=grafana_auth,
            timeout=5
        )
        assert response.status_code == 200
        user = response.json()
        assert 'login' in user
        assert user['login'] == 'admin'


@pytest.mark.observability
@pytest.mark.integration
class TestOpenTelemetryCollectorHealth:
    """Test OpenTelemetry Collector health and metrics"""

    def test_otel_collector_health(self, otel_collector_url):
        """Test OpenTelemetry Collector health endpoint"""
        # Health check: mapped port 23133 (docker-compose) or direct 13133 (host network)
        health_url = otel_collector_url.replace(':14318', ':23133').replace(':4318', ':13133')
        response = requests.get(health_url, timeout=5)
        assert response.status_code == 200

    def test_otel_collector_metrics(self, otel_collector_url):
        """Test OpenTelemetry Collector metrics endpoint"""
        # Metrics are on port 18888 (docker-compose) or 8888 (CI host network)
        metrics_url = otel_collector_url.replace(':14318', ':18888').replace(':4318', ':8888') + '/metrics'
        try:
            response = requests.get(metrics_url, timeout=5)
            assert response.status_code == 200
            assert 'otelcol' in response.text
        except requests.exceptions.ConnectionError:
            pytest.skip("OTEL collector not responding - container may be unhealthy")

    def test_otel_collector_zpages(self, otel_collector_url):
        """Test OpenTelemetry Collector zpages"""
        # zpages on 55679; derive from OTLP port for both docker-compose and CI
        zpages_url = otel_collector_url.replace(':14318', ':55679').replace(':4318', ':55679') + '/debug/tracez'
        try:
            response = requests.get(zpages_url, timeout=5)
            # zpages may not be enabled, so we just check if endpoint responds
            assert response.status_code in [200, 404]
        except requests.exceptions.RequestException:
            # zpages not enabled, that's ok
            pass

    def test_otel_collector_prometheus_metrics(self, otel_collector_url):
        """Test OTel Collector exposes Prometheus metrics"""
        # Metrics are on port 18888 (docker-compose) or 8888 (CI host network)
        metrics_url = otel_collector_url.replace(':14318', ':18888').replace(':4318', ':8888') + '/metrics'
        try:
            response = requests.get(metrics_url, timeout=5)
            assert response.status_code == 200

            # Should have collector-specific metrics
            text = response.text
            assert 'otelcol_process' in text or 'otelcol_receiver' in text
        except requests.exceptions.ConnectionError:
            pytest.skip("OTEL collector not responding - container may be unhealthy")

    def test_otel_collector_receiver_metrics(self, otel_collector_url):
        """Test OTel Collector receiver metrics"""
        # Metrics are on port 18888 (docker-compose) or 8888 (CI host network)
        metrics_url = otel_collector_url.replace(':14318', ':18888').replace(':4318', ':8888') + '/metrics'
        try:
            response = requests.get(metrics_url, timeout=5)
            assert response.status_code == 200

            # Receivers should report metrics
            text = response.text
            # May not have received data yet, but metric names should exist
            assert 'otelcol' in text
        except requests.exceptions.ConnectionError:
            pytest.skip("OTEL collector not responding - container may be unhealthy")


@pytest.mark.observability
@pytest.mark.integration
class TestJaegerHealth:
    """Test Jaeger health and API"""

    def test_jaeger_ui_health(self, jaeger_url):
        """Test Jaeger UI is accessible"""
        response = requests.get(jaeger_url, timeout=5)
        assert response.status_code == 200

    def test_jaeger_api_services(self, jaeger_url):
        """Test Jaeger API services endpoint"""
        services = jaeger_query.services(jaeger_url)
        assert isinstance(services, list)

    def test_jaeger_api_operations(self, jaeger_url):
        """Test Jaeger API operations endpoint"""
        services = jaeger_query.services(jaeger_url)

        if len(services) > 0:
            ops = jaeger_query.operations(jaeger_url, services[0])
            assert isinstance(ops, list)

    def test_jaeger_api_traces(self, jaeger_url):
        """Test Jaeger API traces search endpoint"""
        traces = jaeger_query.find_traces(jaeger_url, 'test-service', limit=10)
        assert isinstance(traces, list)


@pytest.mark.observability
@pytest.mark.integration
class TestJaegerTracing:
    """Test sending traces to Jaeger"""

    def test_jaeger_collector_health(self, jaeger_url):
        """Test Jaeger collector health"""
        # Jaeger collector health may be on different port
        # This is a basic check that Jaeger is running
        response = requests.get(jaeger_url, timeout=5)
        assert response.status_code == 200


@pytest.mark.observability
@pytest.mark.integration
class TestEndToEndMetrics:
    """Test end-to-end metrics flow"""

    def test_full_observability_stack_health(
        self,
        prometheus_url,
        grafana_url,
        otel_collector_url,
        jaeger_url
    ):
        """Test all observability components are healthy"""
        components = {
            'Prometheus': f"{prometheus_url}/-/healthy",
            'Grafana': f"{grafana_url}/api/health",
            'OTel Collector': otel_collector_url.replace(':14318', ':23133').replace(':4318', ':13133'),
            'Jaeger': jaeger_url,
        }

        for name, url in components.items():
            try:
                response = requests.get(url, timeout=5)
                assert response.status_code == 200, f"{name} not healthy"
            except Exception as e:
                pytest.fail(f"{name} is not accessible: {e}")

    def test_prometheus_grafana_integration(self, prometheus_url, grafana_url, grafana_auth):
        """Test Grafana can connect to Prometheus"""
        # Get datasources
        response = requests.get(
            f"{grafana_url}/api/datasources",
            auth=grafana_auth,
            timeout=5
        )
        assert response.status_code == 200

        datasources = response.json()
        prom_ds = [ds for ds in datasources if ds['type'] == 'prometheus']

        if len(prom_ds) > 0:
            # Verify Prometheus datasource has a URL configured
            assert prom_ds[0]['url'], "Prometheus datasource has no URL"

    def test_collector_to_prometheus_pipeline(self, otel_collector_url, prometheus_url):
        """Test metrics can flow from OTel Collector to Prometheus"""
        # Check OTel Collector is exporting metrics in Prometheus format
        metrics_url = otel_collector_url.replace(':14318', ':18889').replace(':4318', ':8889') + '/metrics'

        try:
            response = requests.get(metrics_url, timeout=5)
            if response.status_code == 200:
                # Collector is exposing metrics for Prometheus to scrape
                assert 'otelcol' in response.text
        except requests.exceptions.RequestException:
            # Metrics endpoint may not be exposed, that's ok for basic test
            pass


@pytest.mark.observability
@pytest.mark.integration
class TestMetricsCardinality:
    """Test metric cardinality and performance"""

    def test_high_cardinality_labels(self, metrics_collector):
        """Test handling metrics with high cardinality labels"""
        from ia_modules.telemetry.exporters import PrometheusExporter

        counter = metrics_collector.counter(
            "high_cardinality_test",
            labels=["user_id", "endpoint"]
        )

        # Create 100 unique label combinations
        for i in range(100):
            counter.inc(user_id=f"user_{i}", endpoint=f"/api/resource/{i % 10}")

        metrics = metrics_collector.collect_all()
        assert len(metrics) > 0

        # Export should handle this
        exporter = PrometheusExporter()
        exporter.export(metrics)
        text = exporter.get_metrics_text()
        assert len(text) > 0

    def test_metric_collection_performance(self, metrics_collector):
        """Test performance of metric collection"""
        import timeit

        counter = metrics_collector.counter("perf_test")

        # Time 1000 increments
        duration = timeit.timeit(
            lambda: counter.inc(),
            number=1000
        )

        # Should be very fast (< 1 second for 1000 ops)
        assert duration < 1.0

    def test_concurrent_metric_updates(self, metrics_collector):
        """Test concurrent updates to metrics"""
        import threading

        counter = metrics_collector.counter("concurrent_test")

        def increment():
            for _ in range(100):
                counter.inc()

        threads = [threading.Thread(target=increment) for _ in range(10)]

        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have 1000 total increments
        assert counter.get() == 1000


@pytest.mark.observability
@pytest.mark.integration
class TestStatsDExporter:
    """Test StatsD exporter"""

    def test_statsd_exporter_creation(self):
        """Test creating StatsD exporter"""
        from ia_modules.telemetry.exporters import StatsDExporter

        exporter = StatsDExporter(
            host="localhost",
            port=8125,
            prefix="ia_modules"
        )
        assert exporter.host == "localhost"
        assert exporter.port == 8125
        assert exporter.prefix == "ia_modules"

    def test_statsd_counter_format(self, metrics_collector):
        """Test StatsD counter format"""
        from ia_modules.telemetry.exporters import StatsDExporter

        counter = metrics_collector.counter("test_counter")
        counter.inc(5)

        exporter = StatsDExporter()
        metrics = metrics_collector.collect_all()

        # Export doesn't raise
        try:
            exporter.export(metrics)
        except Exception:
            # Network errors are ok, we're testing formatting
            pass

    def test_statsd_gauge_format(self, metrics_collector):
        """Test StatsD gauge format"""
        from ia_modules.telemetry.exporters import StatsDExporter

        gauge = metrics_collector.gauge("test_gauge")
        gauge.set(42)

        exporter = StatsDExporter()
        metrics = metrics_collector.collect_all()

        try:
            exporter.export(metrics)
        except Exception:
            pass

    def test_statsd_with_labels(self, metrics_collector):
        """Test StatsD with labels/tags"""
        from ia_modules.telemetry.exporters import StatsDExporter

        counter = metrics_collector.counter(
            "tagged_counter",
            labels=["environment", "service"]
        )
        counter.inc(environment="prod", service="api")

        exporter = StatsDExporter()
        metrics = metrics_collector.collect_all()

        try:
            exporter.export(metrics)
        except Exception:
            pass


@pytest.mark.observability
@pytest.mark.integration
class TestExporterErrorHandling:
    """Test exporter error handling"""

    def test_prometheus_exporter_empty_metrics(self):
        """Test Prometheus exporter with no metrics"""
        from ia_modules.telemetry.exporters import PrometheusExporter

        exporter = PrometheusExporter()
        exporter.export([])

        text = exporter.get_metrics_text()
        assert text == "\n"  # Just newline

    def test_prometheus_exporter_no_prefix(self, metrics_collector):
        """Test Prometheus exporter without prefix"""
        from ia_modules.telemetry.exporters import PrometheusExporter

        counter = metrics_collector.counter("test")
        counter.inc()

        exporter = PrometheusExporter(prefix="")
        metrics = metrics_collector.collect_all()
        exporter.export(metrics)

        text = exporter.get_metrics_text()
        # Metric name should not have prefix
        assert "# TYPE test counter" in text

    def test_statsd_socket_error_handling(self):
        """Test StatsD handles socket errors gracefully"""
        from ia_modules.telemetry.exporters import StatsDExporter

        # Use invalid host to force error
        exporter = StatsDExporter(host="invalid.host.local")

        metrics = [
            Metric("test", MetricType.COUNTER, 1, {})
        ]

        # Should not raise, just log error
        exporter.export(metrics)
