"""
Tests for telemetry metrics collection
"""

from ia_modules.telemetry import (
    MetricsCollector,
    Counter,
    Gauge,
    Histogram,
    Summary,
    MetricType
)


class TestCounter:
    """Test Counter metric"""

    def test_counter_creation(self):
        """Test creating a counter"""
        counter = Counter("requests_total", help_text="Total requests")
        assert counter.name == "requests_total"
        assert counter.help_text == "Total requests"

    def test_counter_increment(self):
        """Test incrementing counter"""
        counter = Counter("test_counter")
        counter.inc()
        assert counter.get() == 1.0

        counter.inc(5.0)
        assert counter.get() == 6.0

    def test_counter_with_labels(self):
        """Test counter with labels"""
        counter = Counter("http_requests", labels=["method", "status"])

        counter.inc(method="GET", status="200")
        counter.inc(method="GET", status="200")
        counter.inc(method="POST", status="201")

        assert counter.get(method="GET", status="200") == 2.0
        assert counter.get(method="POST", status="201") == 1.0
        assert counter.get(method="GET", status="404") == 0.0

    def test_counter_collect(self):
        """Test collecting counter metrics"""
        counter = Counter("test_counter", labels=["env"])
        counter.inc(env="prod")
        counter.inc(env="dev")

        metrics = counter.collect()
        assert len(metrics) == 2
        assert all(m.metric_type == MetricType.COUNTER for m in metrics)


class TestGauge:
    """Test Gauge metric"""

    def test_gauge_set(self):
        """Test setting gauge value"""
        gauge = Gauge("temperature")
        gauge.set(25.5)
        assert gauge.get() == 25.5

        gauge.set(30.0)
        assert gauge.get() == 30.0

    def test_gauge_inc_dec(self):
        """Test incrementing and decrementing gauge"""
        gauge = Gauge("queue_depth")
        gauge.set(10.0)

        gauge.inc()
        assert gauge.get() == 11.0

        gauge.inc(5.0)
        assert gauge.get() == 16.0

        gauge.dec(3.0)
        assert gauge.get() == 13.0

    def test_gauge_with_labels(self):
        """Test gauge with labels"""
        gauge = Gauge("memory_usage_bytes", labels=["instance"])

        gauge.set(1024, instance="server1")
        gauge.set(2048, instance="server2")

        assert gauge.get(instance="server1") == 1024
        assert gauge.get(instance="server2") == 2048

    def test_gauge_collect(self):
        """Test collecting gauge metrics"""
        gauge = Gauge("test_gauge", labels=["region"])
        gauge.set(100, region="us-east")
        gauge.set(200, region="us-west")

        metrics = gauge.collect()
        assert len(metrics) == 2
        assert all(m.metric_type == MetricType.GAUGE for m in metrics)


class TestHistogram:
    """Test Histogram metric"""

    def test_histogram_observe(self):
        """Test observing values in histogram"""
        histogram = Histogram("request_duration_seconds")

        histogram.observe(0.1)
        histogram.observe(0.5)
        histogram.observe(1.5)

        metrics = histogram.collect()
        assert len(metrics) == 1

        metric = metrics[0]
        assert metric.metric_type == MetricType.HISTOGRAM
        assert isinstance(metric.value, dict)
        assert metric.value['count'] == 3
        assert metric.value['sum'] == 2.1

    def test_histogram_with_labels(self):
        """Test histogram with labels"""
        histogram = Histogram("http_duration_seconds", labels=["endpoint"])

        histogram.observe(0.1, endpoint="/api/users")
        histogram.observe(0.2, endpoint="/api/users")
        histogram.observe(0.5, endpoint="/api/posts")

        metrics = histogram.collect()
        assert len(metrics) == 2

    def test_histogram_buckets(self):
        """Test histogram bucket counting"""
        histogram = Histogram(
            "test_histogram",
            buckets=[0.1, 0.5, 1.0, 5.0]
        )

        histogram.observe(0.05)  # Below 0.1
        histogram.observe(0.3)   # Below 0.5
        histogram.observe(0.8)   # Below 1.0
        histogram.observe(2.0)   # Below 5.0

        metrics = histogram.collect()
        metric = metrics[0]
        buckets = metric.value['buckets']

        assert buckets[0.1] >= 1  # At least one value <= 0.1
        assert buckets[0.5] >= 2  # At least two values <= 0.5
        assert buckets[1.0] >= 3  # At least three values <= 1.0
        assert buckets[5.0] >= 4  # All four values <= 5.0


class TestSummary:
    """Test Summary metric"""

    def test_summary_observe(self):
        """Test observing values in summary"""
        summary = Summary("request_duration_seconds")

        summary.observe(0.1)
        summary.observe(0.5)
        summary.observe(1.0)

        metrics = summary.collect()
        assert len(metrics) == 1

        metric = metrics[0]
        assert metric.metric_type == MetricType.SUMMARY
        assert isinstance(metric.value, dict)
        assert metric.value['count'] == 3
        assert metric.value['sum'] == 1.6

    def test_summary_quantiles(self):
        """Test summary quantile calculation"""
        summary = Summary(
            "test_summary",
            quantiles=[0.5, 0.9, 0.99]
        )

        # Add 100 values
        for i in range(100):
            summary.observe(i)

        metrics = summary.collect()
        metric = metrics[0]
        quantiles = metric.value['quantiles']

        assert 0.5 in quantiles  # Median
        assert 0.9 in quantiles  # P90
        assert 0.99 in quantiles  # P99

        # Median should be around 50
        assert 45 <= quantiles[0.5] <= 55

    def test_summary_with_labels(self):
        """Test summary with labels"""
        summary = Summary("latency_seconds", labels=["service"])

        summary.observe(0.1, service="api")
        summary.observe(0.2, service="api")
        summary.observe(0.5, service="db")

        metrics = summary.collect()
        assert len(metrics) == 2


class TestMetricsCollector:
    """Test MetricsCollector"""

    def test_collector_creation(self):
        """Test creating metrics collector"""
        collector = MetricsCollector()
        assert collector is not None

    def test_collector_get_or_create_counter(self):
        """Test getting or creating counter"""
        collector = MetricsCollector()

        counter1 = collector.counter("requests_total")
        counter2 = collector.counter("requests_total")

        assert counter1 is counter2  # Same instance

    def test_collector_get_or_create_gauge(self):
        """Test getting or creating gauge"""
        collector = MetricsCollector()

        gauge1 = collector.gauge("memory_usage")
        gauge2 = collector.gauge("memory_usage")

        assert gauge1 is gauge2  # Same instance

    def test_collector_get_or_create_histogram(self):
        """Test getting or creating histogram"""
        collector = MetricsCollector()

        histogram1 = collector.histogram("request_duration")
        histogram2 = collector.histogram("request_duration")

        assert histogram1 is histogram2  # Same instance

    def test_collector_get_or_create_summary(self):
        """Test getting or creating summary"""
        collector = MetricsCollector()

        summary1 = collector.summary("latency")
        summary2 = collector.summary("latency")

        assert summary1 is summary2  # Same instance

    def test_collector_collect_all(self):
        """Test collecting all metrics"""
        collector = MetricsCollector()

        # Create and use metrics
        counter = collector.counter("requests", labels=["method"])
        counter.inc(method="GET")
        counter.inc(method="POST")

        gauge = collector.gauge("temperature")
        gauge.set(25.5)

        # Collect all
        metrics = collector.collect_all()
        assert len(metrics) >= 3  # At least 2 counter + 1 gauge

    def test_collector_get_metric(self):
        """Test getting a specific metric"""
        collector = MetricsCollector()

        counter = collector.counter("test_counter")
        retrieved = collector.get_metric("test_counter")

        assert retrieved is counter

    def test_collector_remove_metric(self):
        """Test removing a metric"""
        collector = MetricsCollector()

        collector.counter("temp_counter")
        assert collector.get_metric("temp_counter") is not None

        collector.remove_metric("temp_counter")
        assert collector.get_metric("temp_counter") is None

    def test_collector_clear(self):
        """Test clearing all metrics"""
        collector = MetricsCollector()

        collector.counter("counter1")
        collector.gauge("gauge1")
        collector.histogram("histogram1")

        collector.clear()
        assert len(collector.collect_all()) == 0


class TestThreadSafety:
    """Test thread safety of metrics"""

    def test_counter_thread_safety(self):
        """Test counter is thread-safe"""
        import threading

        counter = Counter("concurrent_counter")

        def increment():
            for _ in range(1000):
                counter.inc()

        threads = [threading.Thread(target=increment) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert counter.get() == 10000

    def test_gauge_thread_safety(self):
        """Test gauge is thread-safe"""
        import threading

        gauge = Gauge("concurrent_gauge")
        gauge.set(0)

        def modify():
            for _ in range(100):
                gauge.inc()
                gauge.dec()

        threads = [threading.Thread(target=modify) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should end up at 0 (inc and dec cancel out)
        assert gauge.get() == 0
