"""
Trend analysis for agent reliability metrics.

Analyzes time-series metric data to identify trends, forecast future values,
and detect performance degradation or improvement patterns.
"""

from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
import statistics
import logging


class TrendDirection(Enum):
    """Direction of trend movement."""
    IMPROVING = "improving"       # Metric is getting better
    DEGRADING = "degrading"       # Metric is getting worse
    STABLE = "stable"             # No significant trend
    VOLATILE = "volatile"         # High variation, no clear trend


@dataclass
class TrendAnalysis:
    """
    Results of trend analysis for a metric.

    Attributes:
        metric_name: Name of analyzed metric
        direction: Trend direction (improving/degrading/stable/volatile)
        slope: Linear regression slope (rate of change per time unit)
        confidence: Confidence in trend (0.0-1.0, based on R²)
        current_value: Most recent metric value
        predicted_value: Predicted value for next period
        trend_strength: Strength of trend (weak/moderate/strong)
        analyzed_at: When analysis was performed
        data_points: Number of data points analyzed
        context: Additional analysis context
    """
    metric_name: str
    direction: TrendDirection
    slope: float
    confidence: float
    current_value: float
    predicted_value: float
    trend_strength: str
    analyzed_at: datetime
    data_points: int
    context: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "metric_name": self.metric_name,
            "direction": self.direction.value,
            "slope": self.slope,
            "confidence": self.confidence,
            "current_value": self.current_value,
            "predicted_value": self.predicted_value,
            "trend_strength": self.trend_strength,
            "analyzed_at": self.analyzed_at.isoformat(),
            "data_points": self.data_points,
            "context": self.context
        }


class TrendAnalyzer:
    """
    Analyze trends in agent reliability metrics.

    Uses linear regression and statistical methods to:
    - Identify trend direction (improving/degrading/stable)
    - Forecast future metric values
    - Detect performance degradation early
    - Measure trend confidence

    Example:
        >>> analyzer = TrendAnalyzer()
        >>>
        >>> # Record metric values over time
        >>> base_time = datetime.now(timezone.utc)
        >>> for i in range(30):
        ...     timestamp = base_time + timedelta(hours=i)
        ...     # Simulate degrading success rate
        ...     value = 0.99 - (i * 0.01)
        ...     analyzer.record_value("svr", value, timestamp)
        >>>
        >>> # Analyze trend
        >>> trend = analyzer.analyze("svr")
        >>> if trend.direction == TrendDirection.DEGRADING:
        ...     print(f"Warning: SVR degrading at {trend.slope:.4f} per hour")
        ...     print(f"Predicted next value: {trend.predicted_value:.2f}")
    """

    def __init__(
        self,
        min_data_points: int = 10,
        lookback_hours: int = 24,
        confidence_threshold: float = 0.7
    ):
        """
        Initialize trend analyzer.

        Args:
            min_data_points: Minimum data points required for analysis
            lookback_hours: Hours of history to analyze
            confidence_threshold: Minimum R² for strong trend classification
        """
        self.min_data_points = min_data_points
        self.lookback_hours = lookback_hours
        self.confidence_threshold = confidence_threshold

        # Metric history: {metric_name: [(value, timestamp), ...]}
        self._history: Dict[str, List[Tuple[float, datetime]]] = {}

        self.logger = logging.getLogger("TrendAnalyzer")

    def record_value(
        self,
        metric_name: str,
        value: float,
        timestamp: Optional[datetime] = None
    ):
        """
        Record a metric value for trend analysis.

        Args:
            metric_name: Name of metric
            value: Metric value
            timestamp: When value was recorded (default: now)
        """
        if timestamp is None:
            timestamp = datetime.now(timezone.utc)

        if metric_name not in self._history:
            self._history[metric_name] = []

        self._history[metric_name].append((value, timestamp))

        # Keep only recent history
        cutoff = datetime.now(timezone.utc) - timedelta(hours=self.lookback_hours * 2)
        self._history[metric_name] = [
            (v, t) for v, t in self._history[metric_name]
            if t >= cutoff
        ]

    def analyze(
        self,
        metric_name: str,
        lookback_hours: Optional[int] = None
    ) -> Optional[TrendAnalysis]:
        """
        Analyze trend for a metric.

        Args:
            metric_name: Metric to analyze
            lookback_hours: Hours of history to analyze (default: use configured)

        Returns:
            TrendAnalysis or None if insufficient data
        """
        if metric_name not in self._history:
            return None

        lookback = lookback_hours or self.lookback_hours
        cutoff = datetime.now(timezone.utc) - timedelta(hours=lookback)

        # Filter to lookback window
        data = [
            (v, t) for v, t in self._history[metric_name]
            if t >= cutoff
        ]

        if len(data) < self.min_data_points:
            self.logger.debug(f"Insufficient data for {metric_name}: {len(data)} < {self.min_data_points}")
            return None

        # Perform linear regression
        slope, intercept, r_squared = self._linear_regression(data)

        # Determine trend direction
        direction = self._classify_direction(slope, r_squared)

        # Calculate trend strength
        trend_strength = self._classify_strength(r_squared)

        # Get current and predicted values
        current_value = data[-1][0]
        current_time = data[-1][1]

        # Predict next value (1 hour ahead)
        next_time = current_time + timedelta(hours=1)
        time_delta = (next_time - data[0][1]).total_seconds() / 3600  # Convert to hours
        predicted_value = slope * time_delta + intercept

        # Calculate volatility
        values = [v for v, _ in data]
        volatility = statistics.stdev(values) if len(values) > 1 else 0

        return TrendAnalysis(
            metric_name=metric_name,
            direction=direction,
            slope=slope,
            confidence=r_squared,
            current_value=current_value,
            predicted_value=predicted_value,
            trend_strength=trend_strength,
            analyzed_at=datetime.now(timezone.utc),
            data_points=len(data),
            context={
                "intercept": intercept,
                "r_squared": r_squared,
                "volatility": volatility,
                "lookback_hours": lookback,
                "time_range": {
                    "start": data[0][1].isoformat(),
                    "end": data[-1][1].isoformat()
                }
            }
        )

    def analyze_all(
        self,
        lookback_hours: Optional[int] = None
    ) -> Dict[str, TrendAnalysis]:
        """
        Analyze trends for all tracked metrics.

        Args:
            lookback_hours: Hours of history to analyze

        Returns:
            Dict mapping metric names to trend analyses
        """
        results = {}

        for metric_name in self._history.keys():
            analysis = self.analyze(metric_name, lookback_hours)
            if analysis:
                results[metric_name] = analysis

        return results

    def forecast(
        self,
        metric_name: str,
        hours_ahead: int = 24
    ) -> Optional[List[Tuple[datetime, float]]]:
        """
        Forecast future metric values.

        Args:
            metric_name: Metric to forecast
            hours_ahead: How many hours to forecast

        Returns:
            List of (timestamp, predicted_value) tuples
        """
        if metric_name not in self._history:
            return None

        data = self._history[metric_name]

        if len(data) < self.min_data_points:
            return None

        # Perform linear regression
        slope, intercept, _ = self._linear_regression(data)

        # Generate forecast
        last_timestamp = data[-1][1]
        forecast_points = []

        for i in range(1, hours_ahead + 1):
            forecast_time = last_timestamp + timedelta(hours=i)
            time_delta = (forecast_time - data[0][1]).total_seconds() / 3600
            forecast_value = slope * time_delta + intercept

            forecast_points.append((forecast_time, forecast_value))

        return forecast_points

    def detect_degradation(
        self,
        metric_name: str,
        threshold: float,
        forecast_hours: int = 24
    ) -> Optional[Dict[str, Any]]:
        """
        Detect if metric will degrade below threshold in near future.

        Args:
            metric_name: Metric to check
            threshold: Threshold value (metric is bad if below this)
            forecast_hours: Hours to forecast ahead

        Returns:
            Dict with degradation details or None if no degradation expected
        """
        forecast = self.forecast(metric_name, forecast_hours)

        if not forecast:
            return None

        # Check if any forecast point falls below threshold
        for timestamp, value in forecast:
            if value < threshold:
                hours_until = (timestamp - datetime.now(timezone.utc)).total_seconds() / 3600

                return {
                    "metric_name": metric_name,
                    "current_value": self._history[metric_name][-1][0],
                    "threshold": threshold,
                    "breach_time": timestamp.isoformat(),
                    "breach_value": value,
                    "hours_until_breach": hours_until,
                    "forecast_hours": forecast_hours
                }

        return None

    def _linear_regression(
        self,
        data: List[Tuple[float, datetime]]
    ) -> Tuple[float, float, float]:
        """
        Perform linear regression on time-series data.

        Args:
            data: List of (value, timestamp) tuples

        Returns:
            Tuple of (slope, intercept, r_squared)
        """
        if len(data) < 2:
            return 0.0, 0.0, 0.0

        # Convert timestamps to hours since first point
        base_time = data[0][1]
        x_values = [
            (t - base_time).total_seconds() / 3600
            for _, t in data
        ]
        y_values = [v for v, _ in data]

        # Calculate means
        x_mean = statistics.mean(x_values)
        y_mean = statistics.mean(y_values)

        # Calculate slope and intercept
        numerator = sum((x - x_mean) * (y - y_mean) for x, y in zip(x_values, y_values))
        denominator = sum((x - x_mean) ** 2 for x in x_values)

        if denominator == 0:
            return 0.0, y_mean, 0.0

        slope = numerator / denominator
        intercept = y_mean - slope * x_mean

        # Calculate R² (coefficient of determination)
        y_pred = [slope * x + intercept for x in x_values]
        ss_res = sum((y - y_p) ** 2 for y, y_p in zip(y_values, y_pred))
        ss_tot = sum((y - y_mean) ** 2 for y in y_values)

        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0.0

        return slope, intercept, max(0.0, r_squared)  # Ensure R² is non-negative

    def _classify_direction(
        self,
        slope: float,
        r_squared: float,
        slope_threshold: float = 0.001
    ) -> TrendDirection:
        """
        Classify trend direction based on slope and confidence.

        Args:
            slope: Linear regression slope
            r_squared: R² value (confidence)
            slope_threshold: Minimum slope to consider as trend

        Returns:
            TrendDirection
        """
        # Low confidence = volatile or stable
        if r_squared < 0.3:
            return TrendDirection.VOLATILE

        # High confidence with near-zero slope = stable
        if abs(slope) < slope_threshold:
            return TrendDirection.STABLE

        # Positive slope = improving (for most metrics)
        # Note: For metrics like CR, HIR where lower is better, caller should invert
        if slope > 0:
            return TrendDirection.IMPROVING
        else:
            return TrendDirection.DEGRADING

    def _classify_strength(self, r_squared: float) -> str:
        """
        Classify trend strength based on R².

        Args:
            r_squared: R² value

        Returns:
            "weak", "moderate", or "strong"
        """
        if r_squared >= self.confidence_threshold:
            return "strong"
        elif r_squared >= 0.4:
            return "moderate"
        else:
            return "weak"

    def get_summary(self) -> Dict[str, Any]:
        """
        Get summary of all tracked metrics.

        Returns:
            Dict with metric summaries
        """
        summary = {}

        for metric_name in self._history.keys():
            data = self._history[metric_name]

            if not data:
                continue

            values = [v for v, _ in data]

            summary[metric_name] = {
                "data_points": len(data),
                "current_value": data[-1][0],
                "mean": statistics.mean(values),
                "stdev": statistics.stdev(values) if len(values) > 1 else 0,
                "min": min(values),
                "max": max(values),
                "time_range": {
                    "start": data[0][1].isoformat(),
                    "end": data[-1][1].isoformat()
                }
            }

        return summary
