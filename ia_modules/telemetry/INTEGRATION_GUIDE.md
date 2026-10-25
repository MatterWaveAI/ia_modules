# Telemetry Integration Guide

Complete guide for integrating telemetry with IA Modules pipelines.

## Table of Contents

1. [Quick Start](#quick-start)
2. [Automatic Instrumentation](#automatic-instrumentation)
3. [Custom Metrics](#custom-metrics)
4. [Export and Monitoring](#export-and-monitoring)
5. [Best Practices](#best-practices)

## Quick Start

### Automatic Telemetry (Default)

Telemetry is enabled by default in all pipelines:

```python
from ia_modules.pipeline import Pipeline
from ia_modules.pipeline.runner import run_pipeline_from_json

# Run pipeline - telemetry automatically enabled
result = await run_pipeline_from_json(
    "my_pipeline.json",
    input_data={"query": "test"}
)

# Metrics and traces collected automatically!
```

### View Collected Metrics

```python
from ia_modules.telemetry import get_telemetry, PrometheusExporter

# Get telemetry instance
telemetry = get_telemetry()

# Export metrics
exporter = PrometheusExporter(prefix="myapp")
exporter.export(telemetry.get_metrics())

# Print Prometheus format
print(exporter.get_metrics_text())
```

### View Collected Traces

```python
from ia_modules.telemetry import get_telemetry

telemetry = get_telemetry()

# Get all spans
for span in telemetry.get_spans():
    print(f"{span.name}: {span.duration:.3f}s - {span.status}")
```

## Automatic Instrumentation

### Pipeline-Level Metrics

Automatically collected for every pipeline execution:

- **Execution Count**: `pipeline_executions_total{pipeline_name, status}`
- **Duration**: `pipeline_duration_seconds{pipeline_name}`
- **Active Pipelines**: `active_pipelines{pipeline_name}`

### Step-Level Metrics

Automatically collected for every step:

- **Step Duration**: `step_duration_seconds{pipeline_name, step_name}`
- **Step Errors**: `step_errors_total{pipeline_name, step_name, error_type}`

### Distributed Tracing

Automatic span creation:

```
pipeline.my_pipeline (trace_id: abc123)
  ├─ step.fetch_data (parent: abc123)
  ├─ step.process_data (parent: abc123)
  └─ step.store_results (parent: abc123)
```

### Disabling Telemetry

```python
from ia_modules.pipeline import Pipeline

# Disable for specific pipeline
pipeline = Pipeline(
    name="my_pipeline",
    steps=steps,
    flow=flow,
    services=services,
    enable_telemetry=False  # Disable telemetry
)
```

## Custom Metrics

### Adding Custom Metrics to Pipeline

```python
from ia_modules.telemetry import get_telemetry

class CustomStep(Step):
    async def run(self, data):
        telemetry = get_telemetry()

        # Track custom business metric
        telemetry.collector.counter(
            "documents_processed",
            labels=["document_type"]
        ).inc(document_type="invoice")

        # Process documents
        result = process_documents(data)

        return result
```

### Adding Custom Trace Attributes

```python
from ia_modules.telemetry import get_telemetry

class APIStep(Step):
    async def run(self, data):
        telemetry = get_telemetry()

        # Get current pipeline span (if any)
        spans = telemetry.get_spans()
        if spans:
            current_span = spans[-1]  # Latest span

            # Add custom attributes
            current_span.set_attribute("api.endpoint", "/users")
            current_span.set_attribute("api.method", "GET")
            current_span.add_event("api_call_started")

            # Make API call
            response = await make_api_call()

            current_span.add_event("api_call_completed", {
                "status_code": response.status,
                "response_size": len(response.body)
            })

        return {"response": response}
```

### Recording Items and Cost During Execution

```python
from ia_modules.pipeline import Pipeline
from ia_modules.telemetry import get_telemetry

# In your pipeline execution
async def run_data_pipeline(input_data):
    pipeline = create_pipeline()  # Your pipeline

    # Run with automatic telemetry
    result = await pipeline.run(input_data)

    # Record additional metrics after execution
    telemetry = get_telemetry()

    # The pipeline context is available during execution
    # But you can also record metrics directly:
    telemetry.items_processed.inc(
        amount=len(result.get("items", [])),
        pipeline_name=pipeline.name
    )

    telemetry.api_calls.inc(
        amount=result.get("api_calls", 0),
        pipeline_name=pipeline.name
    )

    return result
```

## Export and Monitoring

### Prometheus Export

#### Manual Export

```python
from ia_modules.telemetry import get_telemetry, PrometheusExporter

telemetry = get_telemetry()
exporter = PrometheusExporter(prefix="myapp", port=9090)

# Export metrics
exporter.export(telemetry.get_metrics())

# Get text format
metrics_text = exporter.get_metrics_text()
```

#### HTTP Endpoint

```python
from http.server import HTTPServer, BaseHTTPRequestHandler
from ia_modules.telemetry import get_telemetry, PrometheusExporter

class MetricsHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == '/metrics':
            telemetry = get_telemetry()
            exporter = PrometheusExporter(prefix="myapp")
            exporter.export(telemetry.get_metrics())

            self.send_response(200)
            self.send_header('Content-Type', 'text/plain; charset=utf-8')
            self.end_headers()
            self.wfile.write(exporter.get_metrics_text().encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()

# Run metrics server
server = HTTPServer(('0.0.0.0', 9090), MetricsHandler)
print("Metrics available at http://localhost:9090/metrics")
server.serve_forever()
```

### CloudWatch Export

```python
from ia_modules.telemetry import get_telemetry, CloudWatchExporter

# Requires: pip install boto3

telemetry = get_telemetry()
exporter = CloudWatchExporter(
    namespace="MyApplication/Pipelines",
    region="us-east-1"
)

# Export to CloudWatch
exporter.export(telemetry.get_metrics())
```

### Datadog Export

```python
from ia_modules.telemetry import get_telemetry, DatadogExporter

# Requires: pip install datadog

telemetry = get_telemetry()
exporter = DatadogExporter(
    api_key="your-api-key",
    app_key="your-app-key",
    prefix="myapp"
)

exporter.export(telemetry.get_metrics())
```

### StatsD Export

```python
from ia_modules.telemetry import get_telemetry, StatsDExporter

telemetry = get_telemetry()
exporter = StatsDExporter(
    host="localhost",
    port=8125,
    prefix="myapp"
)

exporter.export(telemetry.get_metrics())
```

## Best Practices

### 1. Use Prefixes to Namespace Metrics

```python
from ia_modules.telemetry import PrometheusExporter

# Good - use prefix for your application
exporter = PrometheusExporter(prefix="myapp")
# Results in: myapp_pipeline_executions_total

# Allows multiple apps in same monitoring system
```

### 2. Export Metrics Regularly

```python
import time
import threading
from ia_modules.telemetry import get_telemetry, PrometheusExporter

def export_metrics_periodically():
    """Background thread to export metrics every 10 seconds"""
    telemetry = get_telemetry()
    exporter = PrometheusExporter(prefix="myapp")

    while True:
        try:
            exporter.export(telemetry.get_metrics())
            # Push to remote system or expose via HTTP
        except Exception as e:
            logger.error(f"Failed to export metrics: {e}")

        time.sleep(10)

# Start background export
thread = threading.Thread(target=export_metrics_periodically, daemon=True)
thread.start()
```

### 3. Monitor Telemetry Overhead

```python
from ia_modules.telemetry import configure_telemetry
import os

# Disable telemetry in development if needed
enable_telemetry = os.getenv("ENABLE_TELEMETRY", "true").lower() == "true"

telemetry = configure_telemetry(enabled=enable_telemetry)

# Or disable for specific high-frequency operations
if high_frequency_operation:
    pipeline = Pipeline(..., enable_telemetry=False)
```

### 4. Use Sampling for High-Volume Traces

```python
import random
from ia_modules.telemetry import get_telemetry

def process_request(request):
    # Only trace 10% of requests
    should_trace = random.random() < 0.1

    if should_trace:
        telemetry = get_telemetry()
        with telemetry.trace_pipeline("request_handler") as ctx:
            result = handle_request(request)
            ctx.set_result(result)
            return result
    else:
        return handle_request(request)
```

### 5. Set Up Alerts

Use the provided Prometheus alert rules:

```bash
# Located at: telemetry/dashboards/alert_rules.yml
cp ia_modules/telemetry/dashboards/alert_rules.yml /etc/prometheus/rules/
```

Key alerts:
- High error rate (>5% for 5min)
- Pipeline duration anomaly (P95 > 300s)
- High cost (>$10/hour)
- No executions (20min)

### 6. Use Grafana Dashboard

Import the provided dashboard:

```bash
# Located at: telemetry/dashboards/grafana_pipeline_dashboard.json
```

Includes 11 panels:
- Pipeline execution rate
- Success rate
- Duration (P95)
- Step duration
- Error rate
- API calls
- Cost per hour
- Throughput
- Memory usage
- CPU usage

### 7. Configure for Production

```python
from ia_modules.telemetry import configure_telemetry, OpenTelemetryTracer, MetricsCollector

# Production setup with OpenTelemetry
collector = MetricsCollector()
tracer = OpenTelemetryTracer(
    service_name="my-pipeline-service",
    endpoint="http://jaeger:4317"  # OTLP endpoint
)

telemetry = configure_telemetry(
    collector=collector,
    tracer=tracer,
    enabled=True
)
```

### 8. Clean Up Resources

```python
from ia_modules.telemetry import get_telemetry

def shutdown_handler():
    """Call on application shutdown"""
    telemetry = get_telemetry()

    # Final export
    exporter.export(telemetry.get_metrics())

    # Clear old spans to free memory
    telemetry.tracer.clear()
```

## Complete Example

```python
import asyncio
from ia_modules.pipeline import Pipeline, Step
from ia_modules.pipeline.core import ExecutionContext
from ia_modules.pipeline.services import ServiceRegistry
from ia_modules.telemetry import (
    configure_telemetry,
    PrometheusExporter,
    SimpleTracer,
    MetricsCollector
)

# Configure telemetry
collector = MetricsCollector()
tracer = SimpleTracer()
telemetry = configure_telemetry(collector=collector, tracer=tracer)

# Define pipeline steps
class FetchDataStep(Step):
    async def run(self, data):
        # Automatically traced and metered
        await asyncio.sleep(0.1)
        return {"items": list(range(100))}

class ProcessDataStep(Step):
    async def run(self, data):
        items = data.get("items", [])
        processed = [x * 2 for x in items]
        return {"processed": processed}

# Create pipeline
steps = [
    FetchDataStep("fetch", {}),
    ProcessDataStep("process", {})
]

flow = {
    "start_at": "fetch",
    "paths": [
        {"from": "fetch", "to": "process"},
        {"from": "process", "to": "end_with_success"}
    ]
}

pipeline = Pipeline(
    "data_pipeline",
    steps,
    flow,
    ServiceRegistry(),
    enable_telemetry=True  # Automatic instrumentation
)

# Run pipeline
async def main():
    await pipeline.run(
        {"input": "test"},
        execution_context=ExecutionContext(execution_id="run-1", pipeline_id="data_pipeline"),
    )

    # Export all metrics to Prometheus
    exporter = PrometheusExporter(prefix="myapp")
    exporter.export(telemetry.get_metrics())

    print("=== Prometheus Metrics ===")
    print(exporter.get_metrics_text())

    print("\n=== Distributed Traces ===")
    for span in telemetry.get_spans():
        print(f"{span.name}: {span.duration:.3f}s - {span.status}")

# Run
asyncio.run(main())
```

## Next Steps

1. Set up Prometheus server to scrape metrics
2. Import Grafana dashboard for visualization
3. Configure alert rules in Prometheus
4. Integrate with your CI/CD for performance tracking
5. Review telemetry overhead and adjust sampling if needed

For more information:
- [Telemetry Guide](TELEMETRY_GUIDE.md) - Detailed API documentation
- [Grafana Dashboard](dashboards/grafana_pipeline_dashboard.json) - Dashboard JSON
- [Alert Rules](dashboards/alert_rules.yml) - Prometheus alerts
