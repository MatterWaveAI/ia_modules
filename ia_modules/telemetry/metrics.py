"""
Metrics Collection Interface

Provides metric types and collection for monitoring pipelines.
"""

from typing import Dict, List, Optional, Union
from dataclasses import dataclass, field
from enum import Enum
import time
import threading
from collections import defaultdict


class MetricType(Enum):
    """Types of metrics"""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    SUMMARY = "summary"


@dataclass
class Metric:
    """Base metric class"""
    name: str
    metric_type: MetricType
    value: Union[int, float, Dict[str, object]]
    labels: Dict[str, str] = field(default_factory=dict)
    timestamp: float = field(default_factory=time.time)
    help_text: str = ""

    def with_labels(self, **labels) -> 'Metric':
        """Return a copy with updated labels"""
        new_labels = {**self.labels, **labels}
        return Metric(
            name=self.name,
            metric_type=self.metric_type,
            value=self.value,
            labels=new_labels,
            timestamp=self.timestamp,
            help_text=self.help_text
        )


class Counter:
    """
    Counter metric - monotonically increasing value

    Use for: requests, errors, completed jobs
    """

    def __init__(self, name: str, help_text: str = "", labels: Optional[List[str]] = None):
        self.name = name
        self.help_text = help_text
        self.label_names = labels or []
        self._values: Dict[tuple, float] = defaultdict(float)
        self._lock = threading.Lock()

    def inc(self, amount: float = 1.0, **labels) -> None:
        """Increment counter"""
        label_key = self._make_key(labels)
        with self._lock:
            self._values[label_key] += amount

    def get(self, **labels) -> float:
        """Get current value"""
        label_key = self._make_key(labels)
        with self._lock:
            return self._values.get(label_key, 0.0)

    def collect(self) -> List[Metric]:
        """Collect all metrics"""
        metrics = []
        with self._lock:
            for label_tuple, value in self._values.items():
                labels = dict(zip(self.label_names, label_tuple))
                metrics.append(Metric(
                    name=self.name,
                    metric_type=MetricType.COUNTER,
                    value=value,
                    labels=labels,
                    help_text=self.help_text
                ))
        return metrics

    def _make_key(self, labels: Dict[str, str]) -> tuple:
        """Create hashable key from labels"""
        return tuple(labels.get(name, "") for name in self.label_names)


class Gauge:
    """
    Gauge metric - value that can go up or down

    Use for: current connections, queue depth, temperature
    """

    def __init__(self, name: str, help_text: str = "", labels: Optional[List[str]] = None):
        self.name = name
        self.help_text = help_text
        self.label_names = labels or []
        self._values: Dict[tuple, float] = defaultdict(float)
        self._lock = threading.Lock()

    def set(self, value: float, **labels) -> None:
        """Set gauge to value"""
        label_key = self._make_key(labels)
        with self._lock:
            self._values[label_key] = value

    def inc(self, amount: float = 1.0, **labels) -> None:
        """Increment gauge"""
        label_key = self._make_key(labels)
        with self._lock:
            self._values[label_key] += amount

    def dec(self, amount: float = 1.0, **labels) -> None:
        """Decrement gauge"""
        label_key = self._make_key(labels)
        with self._lock:
            self._values[label_key] -= amount

    def get(self, **labels) -> float:
        """Get current value"""
        label_key = self._make_key(labels)
        with self._lock:
            return self._values.get(label_key, 0.0)

    def collect(self) -> List[Metric]:
        """Collect all metrics"""
        metrics = []
        with self._lock:
            for label_tuple, value in self._values.items():
                labels = dict(zip(self.label_names, label_tuple))
                metrics.append(Metric(
                    name=self.name,
                    metric_type=MetricType.GAUGE,
                    value=value,
                    labels=labels,
                    help_text=self.help_text
                ))
        return metrics

    def _make_key(self, labels: Dict[str, str]) -> tuple:
        """Create hashable key from labels"""
        return tuple(labels.get(name, "") for name in self.label_names)


class Histogram:
    """
    Histogram metric - observations in buckets

    Use for: request duration, response size
    """

    def __init__(
        self,
        name: str,
        help_text: str = "",
        labels: Optional[List[str]] = None,
        buckets: Optional[List[float]] = None
    ):
        self.name = name
        self.help_text = help_text
        self.label_names = labels or []
        self.buckets = buckets or [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0]

        self._buckets: Dict[tuple, List[int]] = {}
        self._sum: Dict[tuple, float] = defaultdict(float)
        self._count: Dict[tuple, int] = defaultdict(int)
        self._lock = threading.Lock()

    def observe(self, value: float, **labels) -> None:
        """Observe a value"""
        label_key = self._make_key(labels)

        with self._lock:
            # Initialize buckets if needed
            if label_key not in self._buckets:
                self._buckets[label_key] = [0] * len(self.buckets)

            # Update sum and count
            self._sum[label_key] += value
            self._count[label_key] += 1

            # Update buckets
            for i, bucket in enumerate(self.buckets):
                if value <= bucket:
                    self._buckets[label_key][i] += 1

    def collect(self) -> List[Metric]:
        """Collect all metrics"""
        metrics = []
        with self._lock:
            for label_tuple in self._sum.keys():
                labels = dict(zip(self.label_names, label_tuple))

                # Create histogram metric with bucket data
                histogram_data = {
                    'sum': self._sum[label_tuple],
                    'count': self._count[label_tuple],
                    'buckets': dict(zip(self.buckets, self._buckets.get(label_tuple, [])))
                }

                metrics.append(Metric(
                    name=self.name,
                    metric_type=MetricType.HISTOGRAM,
                    value=histogram_data,
                    labels=labels,
                    help_text=self.help_text
                ))
        return metrics

    def _make_key(self, labels: Dict[str, str]) -> tuple:
        """Create hashable key from labels"""
        return tuple(labels.get(name, "") for name in self.label_names)


class Summary:
    """
    Summary metric - observations with quantiles

    Use for: request duration (with percentiles)
    """

    def __init__(
        self,
        name: str,
        help_text: str = "",
        labels: Optional[List[str]] = None,
        quantiles: Optional[List[float]] = None
    ):
        self.name = name
        self.help_text = help_text
        self.label_names = labels or []
        self.quantiles = quantiles or [0.5, 0.9, 0.95, 0.99]

        self._observations: Dict[tuple, List[float]] = defaultdict(list)
        self._sum: Dict[tuple, float] = defaultdict(float)
        self._count: Dict[tuple, int] = defaultdict(int)
        self._lock = threading.Lock()

    def observe(self, value: float, **labels) -> None:
        """Observe a value"""
        label_key = self._make_key(labels)

        with self._lock:
            self._observations[label_key].append(value)
            self._sum[label_key] += value
            self._count[label_key] += 1

    def collect(self) -> List[Metric]:
        """Collect all metrics with calculated quantiles"""
        metrics = []
        with self._lock:
            for label_tuple in self._sum.keys():
                labels = dict(zip(self.label_names, label_tuple))
                observations = sorted(self._observations[label_tuple])

                # Calculate quantiles
                quantile_values = {}
                for q in self.quantiles:
                    idx = int(len(observations) * q)
                    if idx < len(observations):
                        quantile_values[q] = observations[idx]

                summary_data = {
                    'sum': self._sum[label_tuple],
                    'count': self._count[label_tuple],
                    'quantiles': quantile_values
                }

                metrics.append(Metric(
                    name=self.name,
                    metric_type=MetricType.SUMMARY,
                    value=summary_data,
                    labels=labels,
                    help_text=self.help_text
                ))
        return metrics

    def _make_key(self, labels: Dict[str, str]) -> tuple:
        """Create hashable key from labels"""
        return tuple(labels.get(name, "") for name in self.label_names)


class MetricsCollector:
    """
    Central metrics collector

    Manages all metrics and provides collection interface
    """

    def __init__(self):
        self._metrics: Dict[str, Union[Counter, Gauge, Histogram, Summary]] = {}
        self._lock = threading.Lock()

    def counter(
        self,
        name: str,
        help_text: str = "",
        labels: Optional[List[str]] = None
    ) -> Counter:
        """Get or create a counter"""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Counter(name, help_text, labels)
            return self._metrics[name]  # type: ignore[return-value]

    def gauge(
        self,
        name: str,
        help_text: str = "",
        labels: Optional[List[str]] = None
    ) -> Gauge:
        """Get or create a gauge"""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Gauge(name, help_text, labels)
            return self._metrics[name]  # type: ignore[return-value]

    def histogram(
        self,
        name: str,
        help_text: str = "",
        labels: Optional[List[str]] = None,
        buckets: Optional[List[float]] = None
    ) -> Histogram:
        """Get or create a histogram"""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Histogram(name, help_text, labels, buckets)
            return self._metrics[name]  # type: ignore[return-value]

    def summary(
        self,
        name: str,
        help_text: str = "",
        labels: Optional[List[str]] = None,
        quantiles: Optional[List[float]] = None
    ) -> Summary:
        """Get or create a summary"""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Summary(name, help_text, labels, quantiles)
            return self._metrics[name]  # type: ignore[return-value]

    def collect_all(self) -> List[Metric]:
        """Collect all metrics from all registered metrics"""
        all_metrics = []
        with self._lock:
            for metric in self._metrics.values():
                all_metrics.extend(metric.collect())
        return all_metrics

    def get_metric(self, name: str) -> Optional[Union[Counter, Gauge, Histogram, Summary]]:
        """Get a metric by name"""
        with self._lock:
            return self._metrics.get(name)

    def remove_metric(self, name: str) -> bool:
        """Remove a metric"""
        with self._lock:
            if name in self._metrics:
                del self._metrics[name]
                return True
            return False

    def clear(self) -> None:
        """Clear all metrics"""
        with self._lock:
            self._metrics.clear()
