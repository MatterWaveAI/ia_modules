"""
OpenTelemetry Metrics Exporter

Export metrics using OpenTelemetry Protocol (OTLP).
Supports gRPC and HTTP protocols.
"""

from typing import List, Optional, Dict, Any
from .metrics import Metric, MetricType
from .exporters import MetricsExporter

try:
    from opentelemetry import metrics as otel_metrics  # noqa: F401
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import (
        PeriodicExportingMetricReader,
        MetricExporter as OTelMetricExporter  # noqa: F401
    )
    from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter as GRPCExporter
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter as HTTPExporter
    from opentelemetry.sdk.resources import Resource

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False


class OpenTelemetryExporter(MetricsExporter):
    """
    Export metrics using OpenTelemetry Protocol (OTLP)

    Supports both gRPC and HTTP protocols for sending metrics
    to OpenTelemetry Collector or compatible backends.

    Args:
        endpoint: OTLP endpoint URL (default: http://localhost:4317 for gRPC)
        protocol: Protocol to use ('grpc' or 'http')
        headers: Optional headers for authentication
        service_name: Name of the service for resource attributes
        service_version: Version of the service
        deployment_environment: Environment (e.g., 'production', 'staging', 'test')
        prefix: Metric name prefix
    """

    def __init__(
        self,
        endpoint: str = "http://localhost:4317",
        protocol: str = "grpc",
        headers: Optional[Dict[str, str]] = None,
        service_name: str = "ia_modules",
        service_version: str = "0.0.4",
        deployment_environment: str = "development",
        prefix: str = "ia_modules"
    ):
        if not OTEL_AVAILABLE:
            raise ImportError(
                "OpenTelemetry packages are required for OpenTelemetryExporter. "
                "Install with: pip install ia_modules[observability]"
            )

        super().__init__(prefix)

        self.endpoint = endpoint
        self.protocol = protocol.lower()
        self.headers = headers or {}
        self.service_name = service_name
        self.service_version = service_version
        self.deployment_environment = deployment_environment

        # Initialize OpenTelemetry components
        self._init_otel()

    def _init_otel(self):
        """Initialize OpenTelemetry SDK components"""
        # Create resource with service information
        resource = Resource.create({
            "service.name": self.service_name,
            "service.version": self.service_version,
            "deployment.environment": self.deployment_environment,
        })

        # Create appropriate exporter based on protocol
        if self.protocol == "grpc":
            otlp_exporter = GRPCExporter(
                endpoint=self.endpoint,
                headers=self.headers
            )
        elif self.protocol == "http":
            otlp_exporter = HTTPExporter(
                endpoint=self.endpoint,
                headers=self.headers
            )
        else:
            raise ValueError(f"Unsupported protocol: {self.protocol}. Use 'grpc' or 'http'")

        # Create metric reader
        self.reader = PeriodicExportingMetricReader(
            exporter=otlp_exporter,
            export_interval_millis=10000  # Export every 10 seconds
        )

        # Create and set meter provider
        self.provider = MeterProvider(
            resource=resource,
            metric_readers=[self.reader]
        )

        # Get meter for creating instruments
        self.meter = self.provider.get_meter(
            name=self.service_name,
            version=self.service_version
        )

        # Cache for metric instruments
        self._instruments: Dict[str, Any] = {}

        self.logger.info(
            f"Initialized OpenTelemetry exporter with {self.protocol} "
            f"protocol to {self.endpoint}"
        )

    def export(self, metrics: List[Metric]) -> None:
        """Export metrics using OpenTelemetry"""
        for metric in metrics:
            try:
                self._export_metric(metric)
            except Exception as e:
                self.logger.error(f"Failed to export metric {metric.name}: {e}")

        # Force flush to send metrics immediately
        self.provider.force_flush()

        self.logger.debug(f"Exported {len(metrics)} metrics via OpenTelemetry")

    def _export_metric(self, metric: Metric):
        """Export a single metric"""
        formatted_name = self.format_metric_name(metric.name)
        instrument_key = f"{formatted_name}_{metric.metric_type.value}"

        # Get or create instrument
        if instrument_key not in self._instruments:
            self._instruments[instrument_key] = self._create_instrument(
                formatted_name,
                metric.metric_type,
                metric.help_text or ""
            )

        instrument = self._instruments[instrument_key]

        # Record metric value with labels as attributes
        attributes = metric.labels or {}

        if metric.metric_type == MetricType.COUNTER:
            # For counters, record the increment
            if isinstance(metric.value, (int, float)):
                instrument.add(metric.value, attributes)

        elif metric.metric_type == MetricType.GAUGE:
            # For gauges, set the current value
            # Note: OpenTelemetry doesn't have a direct gauge in metrics API
            # We use UpDownCounter or Observable gauge
            if hasattr(instrument, 'add') and isinstance(metric.value, (int, float)):
                # UpDownCounter
                instrument.add(metric.value, attributes)
            else:
                # Observable gauge - value will be read by callback
                pass

        elif metric.metric_type in [MetricType.HISTOGRAM, MetricType.SUMMARY]:
            # For histograms/summaries, record the observation
            if isinstance(metric.value, dict):
                # Extract individual observations if available
                if 'observations' in metric.value:
                    observations = metric.value['observations']
                    if isinstance(observations, list):
                        for obs in observations:
                            if isinstance(obs, (int, float)):
                                instrument.record(obs, attributes)
                elif 'sum' in metric.value and 'count' in metric.value:
                    # Approximate by recording sum/count times
                    sum_val = metric.value['sum']
                    count_val = metric.value['count']
                    if isinstance(sum_val, (int, float)) and isinstance(count_val, (int, float)):
                        avg = sum_val / max(count_val, 1)
                        instrument.record(avg, attributes)
            elif isinstance(metric.value, (int, float)):
                # Simple value
                instrument.record(float(metric.value), attributes)

    def _create_instrument(
        self,
        name: str,
        metric_type: MetricType,
        description: str
    ):
        """Create an OpenTelemetry instrument for the given metric type"""
        if metric_type == MetricType.COUNTER:
            return self.meter.create_counter(
                name=name,
                description=description,
                unit="1"
            )

        elif metric_type == MetricType.GAUGE:
            # Use UpDownCounter for gauges that can increase and decrease
            return self.meter.create_up_down_counter(
                name=name,
                description=description,
                unit="1"
            )

        elif metric_type in [MetricType.HISTOGRAM, MetricType.SUMMARY]:
            return self.meter.create_histogram(
                name=name,
                description=description,
                unit="1"
            )

        else:
            raise ValueError(f"Unsupported metric type: {metric_type}")

    def shutdown(self):
        """Shutdown the exporter and flush remaining metrics"""
        if hasattr(self, 'provider'):
            self.provider.shutdown()
            self.logger.info("OpenTelemetry exporter shut down")


class PrometheusRemoteWriteExporter(MetricsExporter):
    """
    Export metrics using Prometheus Remote Write protocol

    This allows sending metrics directly to Prometheus or compatible
    systems like Cortex, Thanos, or Mimir.
    """

    def __init__(
        self,
        endpoint: str,
        headers: Optional[Dict[str, str]] = None,
        prefix: str = "ia_modules"
    ):
        super().__init__(prefix)
        self.endpoint = endpoint
        self.headers = headers or {}

        try:
            from prometheus_client import CollectorRegistry, push_to_gateway
            from prometheus_client import Counter, Gauge, Histogram

            self.registry = CollectorRegistry()
            self.push_to_gateway = push_to_gateway
            self._metric_types = {
                'counter': Counter,
                'gauge': Gauge,
                'histogram': Histogram
            }
            self._collectors: Dict[str, Any] = {}

        except ImportError:
            raise ImportError(
                "prometheus_client is required for PrometheusRemoteWriteExporter. "
                "Install with: pip install ia_modules[observability]"
            )

    def export(self, metrics: List[Metric]) -> None:
        """Export metrics using Prometheus Remote Write"""
        for metric in metrics:
            try:
                self._export_metric(metric)
            except Exception as e:
                self.logger.error(f"Failed to export metric {metric.name}: {e}")

        # Push to gateway
        try:
            self.push_to_gateway(
                self.endpoint,
                job='ia_modules',
                registry=self.registry,
                timeout=5
            )
            self.logger.debug(f"Pushed {len(metrics)} metrics to Prometheus gateway")
        except Exception as e:
            self.logger.error(f"Failed to push metrics to gateway: {e}")

    def _export_metric(self, metric: Metric):
        """Export a single metric to Prometheus"""
        formatted_name = self.format_metric_name(metric.name)

        # Get or create collector
        if formatted_name not in self._collectors:
            self._collectors[formatted_name] = self._create_collector(
                formatted_name,
                metric.metric_type,
                metric.help_text or "",
                list(metric.labels.keys()) if metric.labels else []
            )

        collector = self._collectors[formatted_name]

        # Record metric
        if metric.labels:
            collector = collector.labels(**metric.labels)

        if metric.metric_type == MetricType.COUNTER:
            if isinstance(metric.value, (int, float)):
                collector.inc(metric.value)
        elif metric.metric_type == MetricType.GAUGE:
            if isinstance(metric.value, (int, float)):
                collector.set(metric.value)
        elif metric.metric_type == MetricType.HISTOGRAM:
            if isinstance(metric.value, dict) and 'observations' in metric.value:
                observations = metric.value['observations']
                if isinstance(observations, list):
                    for obs in observations:
                        if isinstance(obs, (int, float)):
                            collector.observe(obs)
            elif isinstance(metric.value, (int, float)):
                collector.observe(float(metric.value))

    def _create_collector(
        self,
        name: str,
        metric_type: MetricType,
        description: str,
        label_names: List[str]
    ):
        """Create a Prometheus collector"""
        if metric_type == MetricType.COUNTER:
            CollectorClass = self._metric_types['counter']
        elif metric_type == MetricType.GAUGE:
            CollectorClass = self._metric_types['gauge']
        elif metric_type in [MetricType.HISTOGRAM, MetricType.SUMMARY]:
            CollectorClass = self._metric_types['histogram']
        else:
            raise ValueError(f"Unsupported metric type: {metric_type}")

        return CollectorClass(
            name=name,
            documentation=description,
            labelnames=label_names,
            registry=self.registry
        )
