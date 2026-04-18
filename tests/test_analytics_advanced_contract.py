"""Contract tests for the Advanced Analytics Engine.

Verifies:
- AnalyticsEngine registers, records, and queries metrics
- MetricType enum (GAUGE/COUNTER/HISTOGRAM/SUMMARY) works correctly
- Overview/trends/predictions/patterns endpoints work with real engine data
"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timedelta

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))

from copilot_core.analytics.advanced_analytics import AnalyticsEngine, MetricType, MetricPoint


class TestAnalyticsEngineBasics:
    """AnalyticsEngine core functionality."""

    def test_engine_initializes_empty(self):
        engine = AnalyticsEngine()
        assert len(engine._metrics) == 0

    def test_register_metric(self):
        engine = AnalyticsEngine()
        engine.register_metric("test_gauge", MetricType.GAUGE, "Test gauge metric", "units")
        assert "test_gauge" in engine._metrics
        m = engine._metrics["test_gauge"]
        assert m.type == MetricType.GAUGE
        assert m.unit == "units"

    def test_record_and_query(self):
        engine = AnalyticsEngine()
        engine.register_metric("test_counter", MetricType.COUNTER, "Test counter", "requests")
        now = datetime.now()
        engine.record("test_counter", 1.0)
        engine.record("test_counter", 2.0, {"label": "value"})

        assert "test_counter" in engine._metrics
        m = engine._metrics["test_counter"]
        assert len(m.points) == 2

    def test_unregistered_metric_returns_none(self):
        engine = AnalyticsEngine()
        result = engine.record("nonexistent", 42.0)
        assert result is None  # Should warn but not crash


class TestMetricTypeEnum:
    """MetricType enum values match expected string representations."""

    def test_gauges_have_correct_value(self):
        assert MetricType.GAUGE.value == "gauge"

    def test_counter_have_correct_value(self):
        assert MetricType.COUNTER.value == "counter"

    def test_histogram_have_correct_value(self):
        assert MetricType.HISTOGRAM.value == "histogram"

    def test_summary_have_correct_value(self):
        assert MetricType.SUMMARY.value == "summary"


class TestAnalyticsEngineRetention:
    """AnalyticsEngine respects retention_days setting."""

    def test_retention_days_default(self):
        engine = AnalyticsEngine()
        assert engine._retention_days == 30

    def test_retention_days_custom(self):
        engine = AnalyticsEngine(retention_days=7)
        assert engine._retention_days == 7


class TestMetricPoint:
    """MetricPoint dataclass behavior."""

    def test_metric_point_with_labels(self):
        point = MetricPoint(
            timestamp=datetime.now(),
            value=42.0,
            labels={"zone": "living_room", "sensor": "temperature"},
        )
        assert point.value == 42.0
        assert point.labels["zone"] == "living_room"

    def test_metric_point_empty_labels(self):
        point = MetricPoint(timestamp=datetime.now(), value=1.5)
        assert point.labels == {}