"""
Metrics Exporters

Export metrics to various monitoring systems.
"""

from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional, Union
import logging
from .metrics import Metric, MetricType


class MetricsExporter(ABC):
    """Base class for metrics exporters"""

    def __init__(self, prefix: str = "ia_modules"):
        self.prefix = prefix
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def export(self, metrics: List[Metric]) -> None:
        """Export metrics to monitoring system"""
        pass

    def format_metric_name(self, name: str) -> str:
        """Format metric name with prefix"""
        if self.prefix:
            return f"{self.prefix}_{name}"
        return name


class PrometheusExporter(MetricsExporter):
    """
    Export metrics in Prometheus format

    Generates Prometheus-compatible text format for scraping.
    """

    def __init__(self, prefix: str = "ia_modules", port: int = 9090):
        super().__init__(prefix)
        self.port = port
        self._metrics_cache: List[str] = []

    def export(self, metrics: List[Metric]) -> None:
        """Export metrics in Prometheus format"""
        lines = []

        # Group metrics by name
        metrics_by_name: Dict[str, List[Metric]] = {}
        for metric in metrics:
            if metric.name not in metrics_by_name:
                metrics_by_name[metric.name] = []
            metrics_by_name[metric.name].append(metric)

        # Format each metric group
        for name, metric_group in metrics_by_name.items():
            formatted_name = self.format_metric_name(name)

            # Add HELP line
            if metric_group[0].help_text:
                lines.append(f"# HELP {formatted_name} {metric_group[0].help_text}")

            # Add TYPE line
            metric_type = self._get_prometheus_type(metric_group[0].metric_type)
            lines.append(f"# TYPE {formatted_name} {metric_type}")

            # Add metric lines
            for metric in metric_group:
                line = self._format_metric_line(formatted_name, metric)
                if line:
                    lines.append(line)

        self._metrics_cache = lines
        self.logger.debug(f"Exported {len(metrics)} metrics in Prometheus format")

    def get_metrics_text(self) -> str:
        """Get metrics as Prometheus text format"""
        return "\n".join(self._metrics_cache) + "\n"

    def _get_prometheus_type(self, metric_type: MetricType) -> str:
        """Convert metric type to Prometheus type"""
        mapping = {
            MetricType.COUNTER: "counter",
            MetricType.GAUGE: "gauge",
            MetricType.HISTOGRAM: "histogram",
            MetricType.SUMMARY: "summary"
        }
        return mapping.get(metric_type, "untyped")

    def _format_metric_line(self, name: str, metric: Metric) -> Optional[str]:
        """Format a single metric line"""
        labels_str = self._format_labels(metric.labels)

        if metric.metric_type in [MetricType.COUNTER, MetricType.GAUGE]:
            return f"{name}{labels_str} {metric.value}"

        elif metric.metric_type == MetricType.HISTOGRAM:
            # Histogram has multiple lines
            lines: List[str] = []
            data = metric.value
            if isinstance(data, dict):
                # Bucket lines
                buckets_data = data.get('buckets', {})
                if isinstance(buckets_data, dict):
                    for bucket, count in buckets_data.items():
                        bucket_labels = {**metric.labels, 'le': str(bucket)}
                        labels_str = self._format_labels(bucket_labels)
                        lines.append(f"{name}_bucket{labels_str} {count}")

                # +Inf bucket
                inf_labels = {**metric.labels, 'le': '+Inf'}
                labels_str = self._format_labels(inf_labels)
                lines.append(f"{name}_bucket{labels_str} {data.get('count', 0)}")

                # Sum and count
                labels_str = self._format_labels(metric.labels)
                lines.append(f"{name}_sum{labels_str} {data.get('sum', 0)}")
                lines.append(f"{name}_count{labels_str} {data.get('count', 0)}")

            return "\n".join(lines)

        elif metric.metric_type == MetricType.SUMMARY:
            # Summary has multiple lines
            lines = []
            data = metric.value
            if isinstance(data, dict):
                # Quantile lines
                quantiles_data = data.get('quantiles', {})
                if isinstance(quantiles_data, dict):
                    for quantile, value in quantiles_data.items():
                        quantile_labels = {**metric.labels, 'quantile': str(quantile)}
                        labels_str = self._format_labels(quantile_labels)
                        lines.append(f"{name}{labels_str} {value}")

                # Sum and count
                labels_str = self._format_labels(metric.labels)
                lines.append(f"{name}_sum{labels_str} {data.get('sum', 0)}")
                lines.append(f"{name}_count{labels_str} {data.get('count', 0)}")

            return "\n".join(lines)

        return None

    def _format_labels(self, labels: Dict[str, str]) -> str:
        """Format labels for Prometheus"""
        if not labels:
            return ""

        label_pairs = [f'{k}="{v}"' for k, v in labels.items()]
        return "{" + ",".join(label_pairs) + "}"


class CloudWatchExporter(MetricsExporter):
    """
    Export metrics to AWS CloudWatch

    Requires boto3 package.
    """

    def __init__(
        self,
        namespace: str = "IAModules",
        region: str = "us-east-1",
        prefix: str = ""
    ):
        super().__init__(prefix)
        self.namespace = namespace
        self.region = region
        self._client = None

    def _get_client(self):
        """Lazy initialize CloudWatch client"""
        if self._client is None:
            try:
                import boto3
                self._client = boto3.client('cloudwatch', region_name=self.region)
            except ImportError:
                raise ImportError("boto3 is required for CloudWatch exporter")
        return self._client

    def export(self, metrics: List[Metric]) -> None:
        """Export metrics to CloudWatch"""
        client = self._get_client()

        metric_data = []
        for metric in metrics:
            data = self._format_cloudwatch_metric(metric)
            if data:
                metric_data.extend(data if isinstance(data, list) else [data])

        # CloudWatch accepts max 20 metrics per request
        for i in range(0, len(metric_data), 20):
            batch = metric_data[i:i + 20]
            try:
                client.put_metric_data(
                    Namespace=self.namespace,
                    MetricData=batch
                )
                self.logger.debug(f"Exported {len(batch)} metrics to CloudWatch")
            except Exception as e:
                self.logger.error(f"Failed to export metrics to CloudWatch: {e}")

    def _format_cloudwatch_metric(self, metric: Metric) -> Optional[Union[Dict[str, Any], List[Dict[str, Any]]]]:
        """Format metric for CloudWatch"""
        formatted_name = self.format_metric_name(metric.name)

        # Convert labels to dimensions
        dimensions = [
            {'Name': key, 'Value': value}
            for key, value in metric.labels.items()
        ]

        if metric.metric_type in [MetricType.COUNTER, MetricType.GAUGE]:
            if isinstance(metric.value, (int, float)):
                return {
                    'MetricName': formatted_name,
                    'Value': float(metric.value),  # type: ignore[arg-type]
                    'Timestamp': metric.timestamp,
                    'Dimensions': dimensions,
                    'Unit': 'None'
                }

        # For histogram/summary, send multiple metrics
        elif metric.metric_type in [MetricType.HISTOGRAM, MetricType.SUMMARY]:
            metrics_data: List[Dict[str, Any]] = []
            if isinstance(metric.value, dict):
                # Send sum and count
                sum_val = metric.value.get('sum', 0)
                count_val = metric.value.get('count', 0)
                metrics_data.append({
                    'MetricName': f"{formatted_name}_sum",
                    'Value': float(sum_val) if isinstance(sum_val, (int, float)) else 0.0,
                    'Timestamp': metric.timestamp,
                    'Dimensions': dimensions,
                    'Unit': 'None'
                })
                metrics_data.append({
                    'MetricName': f"{formatted_name}_count",
                    'Value': float(count_val) if isinstance(count_val, (int, float)) else 0.0,
                    'Timestamp': metric.timestamp,
                    'Dimensions': dimensions,
                    'Unit': 'Count'
                })
            return metrics_data

        return None


class DatadogExporter(MetricsExporter):
    """
    Export metrics to Datadog

    Requires datadog package.
    """

    def __init__(self, api_key: str, app_key: str, prefix: str = "ia_modules"):
        super().__init__(prefix)
        self.api_key = api_key
        self.app_key = app_key

        try:
            from datadog import initialize, api
            initialize(api_key=self.api_key, app_key=self.app_key)
            self._api = api
        except ImportError:
            raise ImportError("datadog package is required for Datadog exporter")

    def export(self, metrics: List[Metric]) -> None:
        """Export metrics to Datadog"""

        for metric in metrics:
            try:
                formatted_name = self.format_metric_name(metric.name)

                if metric.metric_type in [MetricType.COUNTER, MetricType.GAUGE]:
                    metric_type = 'count' if metric.metric_type == MetricType.COUNTER else 'gauge'

                    self._api.Metric.send(
                        metric=formatted_name,
                        points=[(metric.timestamp, metric.value)],
                        type=metric_type,
                        tags=[f"{k}:{v}" for k, v in metric.labels.items()]
                    )

                self.logger.debug(f"Exported metric {formatted_name} to Datadog")
            except Exception as e:
                self.logger.error(f"Failed to export metric to Datadog: {e}")


class StatsDExporter(MetricsExporter):
    """
    Export metrics to StatsD

    Uses UDP to send metrics to StatsD server.
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 8125,
        prefix: str = "ia_modules"
    ):
        super().__init__(prefix)
        self.host = host
        self.port = port
        self._socket = None

    def _get_socket(self):
        """Get UDP socket"""
        if self._socket is None:
            import socket
            self._socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        return self._socket

    def export(self, metrics: List[Metric]) -> None:
        """Export metrics to StatsD"""
        sock = self._get_socket()

        for metric in metrics:
            message = self._format_statsd_metric(metric)
            if message:
                try:
                    sock.sendto(message.encode('utf-8'), (self.host, self.port))
                except Exception as e:
                    self.logger.error(f"Failed to send metric to StatsD: {e}")

        self.logger.debug(f"Exported {len(metrics)} metrics to StatsD")

    def _format_statsd_metric(self, metric: Metric) -> Optional[str]:
        """Format metric in StatsD format"""
        formatted_name = self.format_metric_name(metric.name)

        # Add labels as tags
        tags = ",".join([f"{k}:{v}" for k, v in metric.labels.items()])
        if tags:
            formatted_name = f"{formatted_name},{tags}"

        if metric.metric_type == MetricType.COUNTER:
            return f"{formatted_name}:{metric.value}|c"
        elif metric.metric_type == MetricType.GAUGE:
            return f"{formatted_name}:{metric.value}|g"
        elif metric.metric_type == MetricType.HISTOGRAM:
            if isinstance(metric.value, dict):
                # Send as timing
                return f"{formatted_name}:{metric.value.get('sum', 0)}|ms"
        elif metric.metric_type == MetricType.SUMMARY:
            if isinstance(metric.value, dict):
                # Send as timing
                return f"{formatted_name}:{metric.value.get('sum', 0)}|ms"

        return None

    def close(self):
        """Close socket"""
        if self._socket:
            self._socket.close()
            self._socket = None
