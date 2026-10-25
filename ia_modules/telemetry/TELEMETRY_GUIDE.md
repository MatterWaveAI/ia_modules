# Telemetry & Monitoring Guide

Complete guide to monitoring and observability for IA Modules pipelines.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Metrics Collection](#metrics-collection)
3. [Distributed Tracing](#distributed-tracing)
4. [Exporters](#exporters)
5. [Dashboards](#dashboards)
6. [Alerts](#alerts)
7. [Best Practices](#best-practices)

## Quick Start

### Basic Metrics Collection

```python
from ia_modules.telemetry import MetricsCollector, PrometheusExporter

# Create collector
collector = MetricsCollector()

# Track pipeline executions
executions = collector.counter(
    "pipeline_executions_total",
    help_text="Total pipeline executions",
    labels=["pipeline_name", "status"]
)

# Track execution duration
duration = collector.histogram(
    "pipeline_duration_seconds",
    help_text="Pipeline execution duration",
    labels=["pipeline_name"]
)

# In your pipeline
executions.inc(pipeline_name="data_processor", status="success")
duration.observe(1.25, pipeline_name="data_processor")

# Export to Prometheus
exporter = PrometheusExporter(prefix="myapp")
exporter.export(collector.collect_all())
print(exporter.get_metrics_text())
```

### Basic Tracing

```python
from ia_modules.telemetry import SimpleTracer, traced, trace_context

tracer = SimpleTracer()

# Trace a function
@traced(tracer, "process_data")
async def process_data(items):
    for item in items:
        with trace_context(tracer, "process_item") as span:
            span.set_attribute("item_id", item.id)
            # Process item
            result = await transform(item)
            span.add_event("transformed", {"status": "ok"})
    return results

# View traces
for span in tracer.get_spans():
    print(f"{span.name}: {span.duration:.3f}s")
```

## Metrics Collection

### Metric Types

#### Counter - Monotonically Increasing
Use for: requests, errors, completed jobs

```python
requests = collector.counter(
    "http_requests_total",
    help_text="Total HTTP requests",
    labels=["method", "endpoint", "status"]
)

requests.inc(method="GET", endpoint="/users", status="200")
requests.inc(method="POST", endpoint="/users", status="201")

# Get current value
current = requests.get(method="GET", endpoint="/users", status="200")
```

#### Gauge - Up and Down Values
Use for: connections, queue depth, temperature

```python
connections = collector.gauge(
    "active_connections",
    help_text="Current active connections"
)

# Connection opened
connections.inc()

# Connection closed
connections.dec()

# Set specific value
connections.set(42)
```

#### Histogram - Observations in Buckets
Use for: request duration, response size

```python
duration = collector.histogram(
    "request_duration_seconds",
    help_text="Request duration",
    labels=["endpoint"],
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0]
)

duration.observe(0.125, endpoint="/api/users")
duration.observe(0.053, endpoint="/api/posts")
```

#### Summary - Observations with Quantiles
Use for: request latency with percentiles

```python
latency = collector.summary(
    "request_latency_seconds",
    help_text="Request latency",
    labels=["service"],
    quantiles=[0.5, 0.9, 0.95, 0.99]
)

latency.observe(0.075, service="api")
# Calculates P50, P90, P95, P99 automatically
```

### Thread Safety

All metrics are thread-safe:

```python
import threading

counter = collector.counter("concurrent_requests")

def handle_request():
    counter.inc()
    # Process request

# Safe to use from multiple threads
threads = [threading.Thread(target=handle_request) for _ in range(100)]
for t in threads:
    t.start()
for t in threads:
    t.join()
```

## Distributed Tracing

### Simple Tracer (Development)

```python
from ia_modules.telemetry import SimpleTracer

tracer = SimpleTracer()

# Start a trace
span = tracer.start_span("fetch_user")
span.set_attribute("user_id", 123)

# Add events
span.add_event("database_query", {"query": "SELECT * FROM users"})
span.add_event("cache_update", {"hit": False})

# Set status
span.set_status("ok")

# End span
tracer.end_span(span)

# Get all spans for a trace
spans = tracer.get_spans(span.trace_id)
```

### OpenTelemetry Integration

```python
from ia_modules.telemetry import OpenTelemetryTracer

# Requires: pip install opentelemetry-api opentelemetry-sdk
tracer = OpenTelemetryTracer(service_name="my_pipeline")

span = tracer.start_span("process_batch")
span.set_attribute("batch_size", 1000)
tracer.end_span(span)
```

### Decorators

```python
@traced(tracer, "expensive_operation")
async def expensive_operation(data):
    # Automatically traced
    result = await process(data)
    return result

# Sync functions work too
@traced(tracer, "sync_operation")
def sync_operation():
    return compute()
```

### Context Managers

```python
with trace_context(tracer, "database_transaction") as span:
    span.set_attribute("table", "users")

    db.insert(record)
    span.add_event("record_inserted")

    db.commit()
    span.add_event("committed")

    # Span automatically closed and marked as "ok"
```

### Error Tracking

```python
with trace_context(tracer, "api_call") as span:
    try:
        response = await api.call()
        span.set_attribute("status_code", response.status)
    except Exception as e:
        # Automatically sets status="error" and captures exception
        raise
```

## Exporters

### Prometheus

```python
from ia_modules.telemetry import PrometheusExporter

exporter = PrometheusExporter(prefix="myapp", port=9090)
exporter.export(collector.collect_all())

# Get metrics text
text = exporter.get_metrics_text()

# Expose via HTTP
from http.server import HTTPServer, BaseHTTPRequestHandler

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics':
            exporter.export(collector.collect_all())
            self.send_response(200)
            self.send_header('Content-Type', 'text/plain')
            self.end_headers()
            self.wfile.write(exporter.get_metrics_text().encode())

server = HTTPServer(('', 9090), MetricsHandler)
server.serve_forever()
```

### CloudWatch (AWS)

```python
from ia_modules.telemetry import CloudWatchExporter

# Requires: pip install boto3
exporter = CloudWatchExporter(
    namespace="MyApplication",
    region="us-east-1"
)

exporter.export(collector.collect_all())
```

### Datadog

```python
from ia_modules.telemetry import DatadogExporter

# Requires: pip install datadog
exporter = DatadogExporter(
    api_key="your-api-key",
    app_key="your-app-key",
    prefix="myapp"
)

exporter.export(collector.collect_all())
```

### StatsD

```python
from ia_modules.telemetry import StatsDExporter

exporter = StatsDExporter(
    host="localhost",
    port=8125,
    prefix="myapp"
)

exporter.export(collector.collect_all())
```

## Dashboards

### Grafana Dashboard

Import the included Grafana dashboard:

```bash
# Located at: telemetry/dashboards/grafana_pipeline_dashboard.json
```

**Panels Included:**
- Pipeline execution rate
- Success rate
- Active pipelines
- Duration (P95)
- Step duration by name
- Error rate by type
- API calls per pipeline
- Cost per hour
- Throughput (items/sec)
- Memory usage
- CPU usage

### Custom Dashboard

```python
# Export metrics for dashboard
from ia_modules.telemetry import MetricsCollector, PrometheusExporter

collector = MetricsCollector()

# Track all pipeline metrics
pipeline_counter = collector.counter("pipeline_executions", labels=["name", "status"])
pipeline_duration = collector.histogram("pipeline_duration_seconds", labels=["name"])
pipeline_cost = collector.counter("pipeline_cost_usd", labels=["name"])

# Export
exporter = PrometheusExporter()
exporter.export(collector.collect_all())
```

## Alerts

### Prometheus Alert Rules

Use the included alert rules:

```bash
# Located at: telemetry/dashboards/alert_rules.yml
```

**Alerts Included:**
- High error rate (>5% for 5min)
- Pipeline duration anomaly (P95 > 300s)
- High cost (>$10/hour)
- Low throughput (<100 items/sec)
- High memory usage (>1GB)
- No executions (20min)
- High step failure rate (>10%)
- API rate limit approaching (>1000/sec)
- High CPU usage (>80%)
- Queue depth growing

### Custom Alerts

```yaml
- alert: CustomAlert
  expr: |
    rate(myapp_custom_metric[5m]) > 100
  for: 10m
  labels:
    severity: warning
  annotations:
    summary: "Custom metric threshold exceeded"
    description: "Value is {{ $value }}"
```

## Best Practices

### 1. Use Meaningful Labels

```python
# Good
requests.inc(method="GET", endpoint="/users", status="200")

# Bad
requests.inc(label1="GET", label2="/users")
```

### 2. Avoid High Cardinality

```python
# Good - limited set of values
requests.inc(status="200")  # 200, 404, 500, etc.

# Bad - unbounded values
requests.inc(user_id="12345")  # Millions of unique values
```

### 3. Use Appropriate Metric Types

```python
# Counters for cumulative values
errors.inc()  # ✓

# Gauges for current state
active_users.set(42)  # ✓

# Histograms for distributions
duration.observe(0.125)  # ✓
```

### 4. Set Histogram Buckets Wisely

```python
# Good - covers expected range
duration = collector.histogram(
    "request_duration_seconds",
    buckets=[0.01, 0.05, 0.1, 0.5, 1.0, 5.0]  # 10ms to 5s
)

# Bad - too granular or wrong range
duration = collector.histogram(
    "request_duration_seconds",
    buckets=[0.001, 0.002, 0.003, ...]  # Too many buckets
)
```

### 5. Add Context to Spans

```python
with trace_context(tracer, "process_batch") as span:
    span.set_attribute("batch_size", len(items))
    span.set_attribute("source", "s3")

    # Add events for important moments
    span.add_event("download_complete", {"bytes": size})
    span.add_event("validation_passed")
```

### 6. Use Prefixes

```python
# Good - use prefixes to namespace metrics
exporter = PrometheusExporter(prefix="myapp")
# Results in: myapp_requests_total

# Allows multiple apps in same Prometheus
```

### 7. Export Regularly

```python
import time
import threading

def export_metrics():
    while True:
        exporter.export(collector.collect_all())
        time.sleep(10)  # Export every 10 seconds

# Run in background
thread = threading.Thread(target=export_metrics, daemon=True)
thread.start()
```

### 8. Monitor Export Errors

```python
try:
    exporter.export(collector.collect_all())
except Exception as e:
    logger.error(f"Failed to export metrics: {e}")
    # Don't let export failures break your app
```

### 9. Use Sampling for High-Frequency Operations

```python
import random

def process_item(item):
    # Only trace 1% of operations
    if random.random() < 0.01:
        with trace_context(tracer, "process_item") as span:
            span.set_attribute("item_id", item.id)
            # Process
    else:
        # Just process, no tracing
        pass
```

### 10. Clean Up Resources

```python
# Close exporters when done
statsd_exporter.close()

# Clear tracer spans if needed
tracer.clear()
```

## Complete Example

```python
import asyncio
from ia_modules.telemetry import (
    MetricsCollector,
    PrometheusExporter,
    SimpleTracer,
    traced,
    trace_context
)

# Setup
collector = MetricsCollector()
tracer = SimpleTracer()
exporter = PrometheusExporter(prefix="pipeline")

# Metrics
executions = collector.counter("executions_total", labels=["pipeline", "status"])
duration = collector.histogram("duration_seconds", labels=["pipeline"])
items_processed = collector.counter("items_total", labels=["pipeline"])

@traced(tracer, "run_pipeline")
async def run_pipeline(pipeline_name, items):
    with trace_context(tracer, "pipeline_execution") as span:
        span.set_attribute("pipeline.name", pipeline_name)
        span.set_attribute("items.count", len(items))

        start = time.time()

        try:
            # Process items
            for item in items:
                with trace_context(tracer, "process_item") as item_span:
                    item_span.set_attribute("item.id", item.id)
                    await process_item(item)
                    items_processed.inc(pipeline=pipeline_name)

            # Success
            elapsed = time.time() - start
            executions.inc(pipeline=pipeline_name, status="success")
            duration.observe(elapsed, pipeline=pipeline_name)
            span.set_status("ok")

        except Exception as e:
            executions.inc(pipeline=pipeline_name, status="error")
            span.set_status("error", str(e))
            raise

# Run
asyncio.run(run_pipeline("data_processor", items))

# Export
exporter.export(collector.collect_all())
print(exporter.get_metrics_text())

# View traces
for span in tracer.get_spans():
    print(f"{span.name}: {span.duration:.3f}s - {span.status}")
```

## Next Steps

- Set up Prometheus server
- Import Grafana dashboards
- Configure alert rules
- Integrate with your pipelines
- Monitor in production

For more information, see the [Integration Guide](INTEGRATION_GUIDE.md).
