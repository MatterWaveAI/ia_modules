"""Tests for trend analysis."""

from datetime import datetime, timedelta, timezone

from ia_modules.reliability.trend_analysis import (
    TrendAnalyzer,
    TrendDirection
)


def test_trend_analyzer_creation():
    """Test creating trend analyzer."""
    analyzer = TrendAnalyzer()

    assert analyzer.min_data_points == 10
    assert analyzer.lookback_hours == 24
    assert analyzer.confidence_threshold == 0.7


def test_record_value():
    """Test recording metric values."""
    analyzer = TrendAnalyzer()

    now = datetime.now(timezone.utc)
    analyzer.record_value("svr", 0.98, now)
    analyzer.record_value("svr", 0.97, now + timedelta(hours=1))

    assert "svr" in analyzer._history
    assert len(analyzer._history["svr"]) == 2


def test_insufficient_data():
    """Test that analysis requires minimum data points."""
    analyzer = TrendAnalyzer(min_data_points=10)

    # Record only a few values
    for i in range(5):
        analyzer.record_value("svr", 0.98)

    # Should return None due to insufficient data
    result = analyzer.analyze("svr")
    assert result is None


def test_analyze_improving_trend():
    """Test detecting improving trend."""
    analyzer = TrendAnalyzer(min_data_points=10)

    base_time = datetime.now(timezone.utc)

    # Record improving metric (increasing values)
    for i in range(20):
        timestamp = base_time + timedelta(hours=i)
        value = 0.80 + (i * 0.01)  # Gradually improving
        analyzer.record_value("svr", value, timestamp)

    trend = analyzer.analyze("svr")

    assert trend is not None
    assert trend.direction == TrendDirection.IMPROVING
    assert trend.slope > 0
    assert trend.data_points == 20


def test_analyze_degrading_trend():
    """Test detecting degrading trend."""
    analyzer = TrendAnalyzer(min_data_points=10)

    base_time = datetime.now(timezone.utc)

    # Record degrading metric (decreasing values)
    for i in range(20):
        timestamp = base_time + timedelta(hours=i)
        value = 0.99 - (i * 0.01)  # Gradually degrading
        analyzer.record_value("success_rate", value, timestamp)

    trend = analyzer.analyze("success_rate")

    assert trend is not None
    assert trend.direction == TrendDirection.DEGRADING
    assert trend.slope < 0


def test_analyze_stable_trend():
    """Test detecting stable trend."""
    analyzer = TrendAnalyzer(min_data_points=10)

    base_time = datetime.now(timezone.utc)

    # Record stable metric (constant with tiny variations)
    for i in range(20):
        timestamp = base_time + timedelta(hours=i)
        value = 0.95 + ((i % 2) * 0.0001)  # Nearly constant
        analyzer.record_value("metric", value, timestamp)

    trend = analyzer.analyze("metric")

    assert trend is not None
    assert trend.direction in [TrendDirection.STABLE, TrendDirection.VOLATILE]


def test_analyze_volatile_trend():
    """Test detecting volatile trend."""
    analyzer = TrendAnalyzer(min_data_points=10)

    base_time = datetime.now(timezone.utc)

    # Record volatile metric (high variation)
    for i in range(20):
        timestamp = base_time + timedelta(hours=i)
        value = 0.50 + ((i % 2) * 0.40)  # Alternating high/low
        analyzer.record_value("volatile_metric", value, timestamp)

    trend = analyzer.analyze("volatile_metric")

    assert trend is not None
    # Could be volatile or stable depending on regression
    assert trend.confidence < 0.7  # Low confidence due to volatility


def test_trend_confidence():
    """Test trend confidence (R²) calculation."""
    analyzer = TrendAnalyzer(min_data_points=10)

    base_time = datetime.now(timezone.utc)

    # Record perfect linear trend
    for i in range(20):
        timestamp = base_time + timedelta(hours=i)
        value = 0.50 + (i * 0.01)  # Perfect linear
        analyzer.record_value("perfect", value, timestamp)

    trend = analyzer.analyze("perfect")

    assert trend is not None
    assert trend.confidence > 0.95  # Very high R² for perfect line


def test_trend_strength_classification():
    """Test trend strength classification."""
    analyzer = TrendAnalyzer(min_data_points=10, confidence_threshold=0.7)

    base_time = datetime.now(timezone.utc)

    # Record strong trend (high R²)
    for i in range(20):
        timestamp = base_time + timedelta(hours=i)
        value = 0.50 + (i * 0.02)
        analyzer.record_value("strong", value, timestamp)

    trend = analyzer.analyze("strong")

    assert trend is not None
    assert trend.trend_strength in ["strong", "moderate"]


def test_predict_next_value():
    """Test prediction of next value."""
    analyzer = TrendAnalyzer(min_data_points=10)

    base_time = datetime.now(timezone.utc)

    # Record linear trend
    for i in range(20):
        timestamp = base_time + timedelta(hours=i)
        value = 0.50 + (i * 0.01)
        analyzer.record_value("metric", value, timestamp)

    trend = analyzer.analyze("metric")

    assert trend is not None
    # Predicted value should be roughly current + slope
    assert trend.predicted_value > trend.current_value


def test_forecast():
    """Test forecasting future values."""
    analyzer = TrendAnalyzer(min_data_points=10)

    base_time = datetime.now(timezone.utc)

    # Record trend
    for i in range(20):
        timestamp = base_time + timedelta(hours=i)
        value = 0.50 + (i * 0.01)
        analyzer.record_value("metric", value, timestamp)

    # Forecast 24 hours ahead
    forecast = analyzer.forecast("metric", hours_ahead=24)

    assert forecast is not None
    assert len(forecast) == 24

    # Each forecast point should have timestamp and value
    for timestamp, value in forecast:
        assert isinstance(timestamp, datetime)
        assert isinstance(value, float)

    # Forecast should extend into future
    assert forecast[0][0] > base_time + timedelta(hours=19)


def test_detect_degradation():
    """Test detecting future degradation below threshold."""
    analyzer = TrendAnalyzer(min_data_points=10)

    base_time = datetime.now(timezone.utc)

    # Record degrading metric that will fall below 0.90
    for i in range(20):
        timestamp = base_time + timedelta(hours=i)
        value = 0.98 - (i * 0.005)  # Will drop below 0.90
        analyzer.record_value("svr", value, timestamp)

    # Detect if will drop below 0.90 threshold
    degradation = analyzer.detect_degradation("svr", threshold=0.90, forecast_hours=24)

    assert degradation is not None
    assert degradation["metric_name"] == "svr"
    assert degradation["threshold"] == 0.90
    assert degradation["hours_until_breach"] > 0


def test_no_degradation_detected():
    """Test when no degradation is expected."""
    analyzer = TrendAnalyzer(min_data_points=10)

    base_time = datetime.now(timezone.utc)

    # Record stable high metric
    for i in range(20):
        timestamp = base_time + timedelta(hours=i)
        value = 0.98
        analyzer.record_value("svr", value, timestamp)

    # Should not detect degradation
    degradation = analyzer.detect_degradation("svr", threshold=0.90, forecast_hours=24)

    assert degradation is None


def test_analyze_all():
    """Test analyzing all tracked metrics."""
    analyzer = TrendAnalyzer(min_data_points=5)

    base_time = datetime.now(timezone.utc)

    # Record multiple metrics
    for i in range(10):
        timestamp = base_time + timedelta(hours=i)
        analyzer.record_value("metric1", 0.50 + (i * 0.01), timestamp)
        analyzer.record_value("metric2", 0.90 - (i * 0.01), timestamp)
        analyzer.record_value("metric3", 0.75, timestamp)  # Stable

    trends = analyzer.analyze_all()

    assert len(trends) == 3
    assert "metric1" in trends
    assert "metric2" in trends
    assert "metric3" in trends

    assert trends["metric1"].direction == TrendDirection.IMPROVING
    assert trends["metric2"].direction == TrendDirection.DEGRADING


def test_get_summary():
    """Test getting summary statistics."""
    analyzer = TrendAnalyzer()

    base_time = datetime.now(timezone.utc)

    # Record values
    for i in range(10):
        timestamp = base_time + timedelta(hours=i)
        analyzer.record_value("metric", 100.0 + i, timestamp)

    summary = analyzer.get_summary()

    assert "metric" in summary
    assert summary["metric"]["data_points"] == 10
    assert summary["metric"]["current_value"] == 109.0
    assert summary["metric"]["min"] == 100.0
    assert summary["metric"]["max"] == 109.0


def test_lookback_window():
    """Test that lookback window filters old data."""
    analyzer = TrendAnalyzer(min_data_points=5, lookback_hours=10)

    base_time = datetime.now(timezone.utc)

    # Record values: some old, some recent
    for i in range(20):
        timestamp = base_time - timedelta(hours=20) + timedelta(hours=i)
        analyzer.record_value("metric", 0.50 + (i * 0.01), timestamp)

    # Analyze with default lookback (10 hours)
    trend = analyzer.analyze("metric")

    assert trend is not None
    # Should only use data from last 10 hours
    assert trend.data_points <= 10


def test_custom_lookback():
    """Test analyzing with custom lookback period."""
    analyzer = TrendAnalyzer(min_data_points=5, lookback_hours=24)

    base_time = datetime.now(timezone.utc)

    # Record 20 hours of data
    for i in range(20):
        timestamp = base_time - timedelta(hours=19) + timedelta(hours=i)
        analyzer.record_value("metric", 0.50 + (i * 0.01), timestamp)

    # Analyze with custom 12-hour lookback
    trend = analyzer.analyze("metric", lookback_hours=12)

    assert trend is not None
    # Should use approximately 12 hours of data
    assert trend.data_points >= 11


def test_trend_to_dict():
    """Test converting trend analysis to dictionary."""
    analyzer = TrendAnalyzer(min_data_points=5)

    base_time = datetime.now(timezone.utc)

    for i in range(10):
        timestamp = base_time + timedelta(hours=i)
        analyzer.record_value("svr", 0.90 + (i * 0.01), timestamp)

    trend = analyzer.analyze("svr")

    data = trend.to_dict()

    assert data["metric_name"] == "svr"
    assert data["direction"] == "improving"
    assert "slope" in data
    assert "confidence" in data
    assert "current_value" in data
    assert "predicted_value" in data
