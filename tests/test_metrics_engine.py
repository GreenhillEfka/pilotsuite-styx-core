"""Tests for Metrics Engine — Slice 37."""
import pytest
from copilot_core.metrics.engine import (
    MetricsEngine,
    MetricType,
    Metric,
    MetricPoint,
    AlertThreshold,
    create_metrics_engine,
)
from datetime import datetime, timezone, timedelta
import time


class TestMetricsEngine:
    """Test metrics engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_metrics_engine()
        assert engine is not None
    
    def test_register_counter(self):
        """Test registering counter metric."""
        engine = MetricsEngine()
        
        engine.register_metric("requests_total", "Total requests", "counter", unit="requests")
        
        metric = engine.get_metric("requests_total")
        
        assert metric is not None
        assert metric["metric_type"] == "counter"
        assert metric["unit"] == "requests"
    
    def test_register_gauge(self):
        """Test registering gauge metric."""
        engine = MetricsEngine()
        
        engine.register_metric("temperature", "Current temperature", "gauge", unit="celsius")
        
        metric = engine.get_metric("temperature")
        
        assert metric is not None
        assert metric["metric_type"] == "gauge"
    
    def test_register_histogram(self):
        """Test registering histogram metric."""
        engine = MetricsEngine()
        
        engine.register_metric(
            "request_duration",
            "Request duration",
            "histogram",
            unit="seconds",
            buckets=[0.1, 0.5, 1.0, 2.5, 5.0, 10.0],
        )
        
        metric = engine.get_metric("request_duration")
        
        assert metric is not None
        assert metric["metric_type"] == "histogram"
    
    def test_increment_counter(self):
        """Test incrementing counter."""
        engine = MetricsEngine()
        
        engine.increment("requests_total", value=1.0)
        engine.increment("requests_total", value=2.0)
        engine.increment("requests_total", value=3.0)
        
        value = engine.get_metric_value("requests_total")
        
        assert value == 6.0
    
    def test_increment_counter_with_labels(self):
        """Test incrementing counter with labels."""
        engine = MetricsEngine()
        
        engine.increment("requests_total", value=1.0, labels={"method": "GET"})
        engine.increment("requests_total", value=2.0, labels={"method": "GET"})
        engine.increment("requests_total", value=3.0, labels={"method": "POST"})
        
        get_value = engine.get_metric_value("requests_total", labels={"method": "GET"})
        post_value = engine.get_metric_value("requests_total", labels={"method": "POST"})
        
        assert get_value == 3.0
        assert post_value == 3.0
    
    def test_set_gauge(self):
        """Test setting gauge value."""
        engine = MetricsEngine()
        
        engine.set_gauge("temperature", value=22.5)
        
        value = engine.get_metric_value("temperature")
        
        assert value == 22.5
    
    def test_set_gauge_up_and_down(self):
        """Test gauge going up and down."""
        engine = MetricsEngine()
        
        engine.set_gauge("temperature", value=20.0)
        engine.set_gauge("temperature", value=25.0)
        engine.set_gauge("temperature", value=18.0)
        
        value = engine.get_metric_value("temperature")
        
        assert value == 18.0
    
    def test_observe_histogram(self):
        """Test observing histogram values."""
        engine = MetricsEngine()
        
        for value in [0.05, 0.15, 0.3, 0.8, 1.5, 3.0, 8.0]:
            engine.observe_histogram("request_duration", value)
        
        metric = engine._metrics["request_duration"]
        
        # Check bucket counts
        assert metric.bucket_counts[0.1] == 1  # Only 0.05
        assert metric.bucket_counts[0.5] == 3  # 0.05, 0.15, 0.3
    
    def test_get_metric_value_aggregation_avg(self):
        """Test getting metric value with avg aggregation."""
        engine = MetricsEngine()
        
        for i in range(5):
            engine.set_gauge("temperature", value=float(i * 10))
        
        value = engine.get_metric_value("temperature", aggregation="avg")
        
        assert value == 20.0  # (0+10+20+30+40)/5
    
    def test_get_metric_value_aggregation_min(self):
        """Test getting metric value with min aggregation."""
        engine = MetricsEngine()
        
        engine.set_gauge("temperature", value=25.0)
        engine.set_gauge("temperature", value=18.0)
        engine.set_gauge("temperature", value=22.0)
        
        value = engine.get_metric_value("temperature", aggregation="min")
        
        assert value == 18.0
    
    def test_get_metric_value_aggregation_max(self):
        """Test getting metric value with max aggregation."""
        engine = MetricsEngine()
        
        engine.set_gauge("temperature", value=25.0)
        engine.set_gauge("temperature", value=18.0)
        engine.set_gauge("temperature", value=22.0)
        
        value = engine.get_metric_value("temperature", aggregation="max")
        
        assert value == 25.0
    
    def test_get_metric_value_aggregation_sum(self):
        """Test getting metric value with sum aggregation."""
        engine = MetricsEngine()
        
        engine.increment("requests_total", value=10.0)
        engine.increment("requests_total", value=20.0)
        engine.increment("requests_total", value=30.0)
        
        value = engine.get_metric_value("requests_total", aggregation="sum")
        
        assert value == 60.0
    
    def test_get_metric_history(self):
        """Test getting metric history."""
        engine = MetricsEngine()
        
        for i in range(10):
            engine.set_gauge("temperature", value=float(i))
        
        history = engine.get_metric_history("temperature", limit=5)
        
        assert len(history) == 5
    
    def test_get_metric_history_with_labels(self):
        """Test getting metric history with labels."""
        engine = MetricsEngine()
        
        engine.set_gauge("temperature", value=20.0, labels={"sensor": "A"})
        engine.set_gauge("temperature", value=21.0, labels={"sensor": "A"})
        engine.set_gauge("temperature", value=25.0, labels={"sensor": "B"})
        
        history = engine.get_metric_history("temperature", labels={"sensor": "A"})
        
        assert len(history) == 2
        assert all(h["labels"]["sensor"] == "A" for h in history)
    
    def test_get_metric_history_time_range(self):
        """Test getting metric history with time range."""
        engine = MetricsEngine()
        
        now = datetime.now(timezone.utc)
        
        for i in range(5):
            engine.set_gauge("temperature", value=float(i))
        
        # Query with time range
        start = (now - timedelta(hours=1)).isoformat()
        end = now.isoformat()
        
        history = engine.get_metric_history("temperature", start_time=start, end_time=end)
        
        assert len(history) >= 1
    
    def test_get_all_metrics(self):
        """Test getting all metrics."""
        engine = MetricsEngine()
        
        engine.register_metric("metric1", "Test 1", "counter")
        engine.register_metric("metric2", "Test 2", "gauge")
        engine.register_metric("metric3", "Test 3", "histogram")
        
        metrics = engine.get_all_metrics()
        
        assert len(metrics) == 3
    
    def test_register_threshold_gt(self):
        """Test registering greater-than threshold."""
        engine = MetricsEngine()
        
        threshold_id = engine.register_threshold(
            metric_name="temperature",
            condition="gt",
            value=30.0,
            severity="warning",
        )
        
        assert threshold_id is not None
        
        thresholds = engine.get_thresholds()
        
        assert len(thresholds) == 1
        assert thresholds[0]["condition"] == "gt"
        assert thresholds[0]["value"] == 30.0
    
    def test_threshold_triggers_alert(self):
        """Test that threshold triggers alert."""
        engine = MetricsEngine()
        
        engine.register_threshold(
            metric_name="temperature",
            condition="gt",
            value=25.0,
            severity="warning",
        )
        
        engine.set_gauge("temperature", value=20.0)  # Below threshold
        engine.set_gauge("temperature", value=30.0)  # Above threshold
        
        alerts = engine.get_alerts()
        
        assert len(alerts) == 1
        assert alerts[0]["metric_name"] == "temperature"
        assert alerts[0]["value"] == 30.0
    
    def test_threshold_does_not_trigger_below(self):
        """Test that threshold does not trigger when below."""
        engine = MetricsEngine()
        
        engine.register_threshold(
            metric_name="temperature",
            condition="gt",
            value=30.0,
            severity="warning",
        )
        
        engine.set_gauge("temperature", value=25.0)  # Below threshold
        
        alerts = engine.get_alerts()
        
        assert len(alerts) == 0
    
    def test_threshold_condition_gte(self):
        """Test greater-than-or-equal threshold."""
        engine = MetricsEngine()
        
        engine.register_threshold(
            metric_name="temperature",
            condition="gte",
            value=25.0,
            severity="warning",
        )
        
        engine.set_gauge("temperature", value=25.0)  # Equal to threshold
        
        alerts = engine.get_alerts()
        
        assert len(alerts) == 1
    
    def test_threshold_condition_lt(self):
        """Test less-than threshold."""
        engine = MetricsEngine()
        
        engine.register_threshold(
            metric_name="temperature",
            condition="lt",
            value=15.0,
            severity="warning",
        )
        
        engine.set_gauge("temperature", value=10.0)  # Below threshold
        
        alerts = engine.get_alerts()
        
        assert len(alerts) == 1
    
    def test_threshold_condition_lte(self):
        """Test less-than-or-equal threshold."""
        engine = MetricsEngine()
        
        engine.register_threshold(
            metric_name="temperature",
            condition="lte",
            value=15.0,
            severity="warning",
        )
        
        engine.set_gauge("temperature", value=15.0)  # Equal to threshold
        
        alerts = engine.get_alerts()
        
        assert len(alerts) == 1
    
    def test_threshold_condition_eq(self):
        """Test equals threshold."""
        engine = MetricsEngine()
        
        engine.register_threshold(
            metric_name="temperature",
            condition="eq",
            value=25.0,
            severity="warning",
        )
        
        engine.set_gauge("temperature", value=25.0)
        
        alerts = engine.get_alerts()
        
        assert len(alerts) == 1
    
    def test_enable_disable_threshold(self):
        """Test enabling/disabling threshold."""
        engine = MetricsEngine()
        
        threshold_id = engine.register_threshold(
            metric_name="temperature",
            condition="gt",
            value=25.0,
        )
        
        # Disable
        result = engine.disable_threshold(threshold_id)
        assert result is True
        
        engine.set_gauge("temperature", value=30.0)
        
        alerts = engine.get_alerts()
        assert len(alerts) == 0  # No alert because disabled
        
        # Enable
        result = engine.enable_threshold(threshold_id)
        assert result is True
        
        engine.set_gauge("temperature", value=35.0)
        
        alerts = engine.get_alerts()
        assert len(alerts) >= 1
    
    def test_register_alert_callback(self):
        """Test registering alert callback."""
        engine = MetricsEngine()
        
        alerts_received = []
        
        def callback(alert):
            alerts_received.append(alert)
        
        engine.register_alert_callback(callback)
        
        engine.register_threshold("temperature", "gt", 25.0)
        engine.set_gauge("temperature", value=30.0)
        
        assert len(alerts_received) == 1
    
    def test_get_alerts_filtered_by_metric(self):
        """Test getting alerts filtered by metric."""
        engine = MetricsEngine()
        
        engine.register_threshold("temperature", "gt", 25.0)
        engine.register_threshold("humidity", "gt", 80.0)
        
        engine.set_gauge("temperature", value=30.0)
        engine.set_gauge("humidity", value=85.0)
        
        temp_alerts = engine.get_alerts(metric_name="temperature")
        
        assert len(temp_alerts) == 1
        assert temp_alerts[0]["metric_name"] == "temperature"
    
    def test_get_alerts_filtered_by_severity(self):
        """Test getting alerts filtered by severity."""
        engine = MetricsEngine()
        
        engine.register_threshold("temperature", "gt", 25.0, severity="warning")
        engine.register_threshold("temperature", "gt", 40.0, severity="critical")
        
        engine.set_gauge("temperature", value=30.0)
        engine.set_gauge("temperature", value=45.0)
        
        critical_alerts = engine.get_alerts(severity="critical")
        
        assert len(critical_alerts) == 1
        assert critical_alerts[0]["severity"] == "critical"
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = MetricsEngine()
        
        engine.register_metric("counter1", "Test", "counter")
        engine.register_metric("gauge1", "Test", "gauge")
        
        engine.increment("counter1", value=10.0)
        engine.set_gauge("gauge1", value=25.0)
        
        stats = engine.get_statistics()
        
        assert stats["total_metrics"] == 2
        assert stats["total_points"] == 2
    
    def test_export_prometheus(self):
        """Test exporting to Prometheus format."""
        engine = MetricsEngine()
        
        engine.register_metric("requests_total", "Total requests", "counter")
        engine.increment("requests_total", value=100.0)
        
        export = engine.export_prometheus()
        
        assert "# HELP requests_total" in export
        assert "# TYPE requests_total counter"
        assert "requests_total" in export
        assert "100.0" in export
    
    def test_export_prometheus_with_labels(self):
        """Test exporting to Prometheus format with labels."""
        engine = MetricsEngine()
        
        engine.increment("requests_total", value=50.0, labels={"method": "GET"})
        engine.increment("requests_total", value=30.0, labels={"method": "POST"})
        
        export = engine.export_prometheus()
        
        assert 'method="GET"' in export
        assert 'method="POST"' in export
    
    def test_export_prometheus_histogram(self):
        """Test exporting histogram to Prometheus format."""
        engine = MetricsEngine()
        
        engine.register_metric("request_duration", "Duration", "histogram",
                             buckets=[0.1, 0.5, 1.0])
        
        for value in [0.05, 0.3, 0.8]:
            engine.observe_histogram("request_duration", value)
        
        export = engine.export_prometheus()
        
        assert "request_duration_bucket" in export
        assert 'le="0.1"' in export
        assert 'le="0.5"' in export
    
    def test_export_json(self):
        """Test exporting to JSON."""
        engine = MetricsEngine()
        
        engine.register_metric("temperature", "Temperature", "gauge")
        engine.set_gauge("temperature", value=22.5)
        
        export = engine.export_json()
        
        assert "temperature" in export
        assert "22.5" in export
    
    def test_cleanup_old_data(self):
        """Test cleaning up old data."""
        engine = MetricsEngine()
        
        # Add some points
        for i in range(10):
            engine.set_gauge("temperature", value=float(i))
        
        # Clean up with cutoff in the future (removes all)
        future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat()
        
        removed = engine.cleanup_old_data(older_than=future)
        
        assert removed == 10
    
    def test_reset_metric(self):
        """Test resetting metric."""
        engine = MetricsEngine()
        
        for i in range(10):
            engine.set_gauge("temperature", value=float(i))
        
        result = engine.reset_metric("temperature")
        
        assert result is True
        
        value = engine.get_metric_value("temperature")
        assert value is None
    
    def test_reset_nonexistent_metric(self):
        """Test resetting nonexistent metric."""
        engine = MetricsEngine()
        
        result = engine.reset_metric("nonexistent")
        
        assert result is False
    
    def test_delete_metric(self):
        """Test deleting metric."""
        engine = MetricsEngine()
        
        engine.register_metric("temperature", "Temperature", "gauge")
        
        result = engine.delete_metric("temperature")
        
        assert result is True
        assert engine.get_metric("temperature") is None
    
    def test_delete_nonexistent_metric(self):
        """Test deleting nonexistent metric."""
        engine = MetricsEngine()
        
        result = engine.delete_metric("nonexistent")
        
        assert result is False
    
    def test_get_nonexistent_metric(self):
        """Test getting nonexistent metric."""
        engine = MetricsEngine()
        
        metric = engine.get_metric("nonexistent")
        
        assert metric is None
    
    def test_get_nonexistent_metric_value(self):
        """Test getting value of nonexistent metric."""
        engine = MetricsEngine()
        
        value = engine.get_metric_value("nonexistent")
        
        assert value is None
    
    def test_get_empty_metric_history(self):
        """Test getting history of metric with no points."""
        engine = MetricsEngine()
        
        engine.register_metric("temperature", "Temperature", "gauge")
        
        history = engine.get_metric_history("temperature")
        
        assert history == []
    
    def test_metric_points_trimmed_to_max(self):
        """Test that metric points are trimmed to max."""
        engine = MetricsEngine(max_points_per_metric=100)
        
        for i in range(200):
            engine.set_gauge("temperature", value=float(i))
        
        metric = engine._metrics["temperature"]
        
        assert len(metric.points) == 100
    
    def test_auto_register_metric_on_increment(self):
        """Test that increment auto-registers metric."""
        engine = MetricsEngine()
        
        engine.increment("auto_counter", value=1.0)
        
        metric = engine.get_metric("auto_counter")
        
        assert metric is not None
        assert metric["metric_type"] == "counter"
    
    def test_auto_register_metric_on_set_gauge(self):
        """Test that set_gauge auto-registers metric."""
        engine = MetricsEngine()
        
        engine.set_gauge("auto_gauge", value=25.0)
        
        metric = engine.get_metric("auto_gauge")
        
        assert metric is not None
        assert metric["metric_type"] == "gauge"
    
    def test_auto_register_metric_on_histogram(self):
        """Test that observe_histogram auto-registers metric."""
        engine = MetricsEngine()
        
        engine.observe_histogram("auto_histogram", value=0.5)
        
        metric = engine.get_metric("auto_histogram")
        
        assert metric is not None
        assert metric["metric_type"] == "histogram"
    
    def test_metric_type_enum_values(self):
        """Test metric type enum values."""
        assert MetricType.COUNTER.value == "counter"
        assert MetricType.GAUGE.value == "gauge"
        assert MetricType.HISTOGRAM.value == "histogram"
        assert MetricType.SUMMARY.value == "summary"
    
    def test_metric_to_dict(self):
        """Test metric serialization."""
        metric = Metric(
            name="test_metric",
            description="Test description",
            metric_type=MetricType.GAUGE,
            unit="units",
            labels=["label1", "label2"],
        )
        
        d = metric.to_dict()
        
        assert d["name"] == "test_metric"
        assert d["metric_type"] == "gauge"
        assert d["unit"] == "units"
    
    def test_metric_point_to_dict(self):
        """Test metric point serialization."""
        point = MetricPoint(
            timestamp="2026-03-31T12:00:00Z",
            value=42.5,
            labels={"sensor": "A"},
        )
        
        d = point.to_dict()
        
        assert d["timestamp"] == "2026-03-31T12:00:00Z"
        assert d["value"] == 42.5
        assert d["labels"]["sensor"] == "A"
    
    def test_alert_threshold_to_dict(self):
        """Test alert threshold serialization."""
        threshold = AlertThreshold(
            threshold_id="thresh_test",
            metric_name="temperature",
            condition="gt",
            value=30.0,
            duration_seconds=60,
            severity="warning",
            enabled=True,
        )
        
        d = threshold.to_dict()
        
        assert d["threshold_id"] == "thresh_test"
        assert d["condition"] == "gt"
        assert d["value"] == 30.0
    
    def test_statistics_by_type(self):
        """Test statistics breakdown by type."""
        engine = MetricsEngine()
        
        engine.register_metric("c1", "Test", "counter")
        engine.register_metric("c2", "Test", "counter")
        engine.register_metric("g1", "Test", "gauge")
        engine.register_metric("h1", "Test", "histogram")
        
        stats = engine.get_statistics()
        
        assert stats["by_type"]["counter"] == 2
        assert stats["by_type"]["gauge"] == 1
        assert stats["by_type"]["histogram"] == 1
    
    def test_alerts_sorted_by_timestamp(self):
        """Test that alerts are sorted by timestamp."""
        engine = MetricsEngine()
        
        engine.register_threshold("temperature", "gt", 20.0)
        
        for i in range(5):
            engine.set_gauge("temperature", value=float(25 + i))
        
        alerts = engine.get_alerts(limit=10)
        
        # Verify sorted (newest first)
        for i in range(len(alerts) - 1):
            assert alerts[i]["timestamp"] >= alerts[i + 1]["timestamp"]
    
    def test_alerts_limited(self):
        """Test that alerts are limited."""
        engine = MetricsEngine()
        
        engine.register_threshold("temperature", "gt", 20.0)
        
        for i in range(50):
            engine.set_gauge("temperature", value=float(25 + i))
        
        alerts = engine.get_alerts(limit=10)
        
        assert len(alerts) == 10
    
    def test_increment_warning_for_non_counter(self):
        """Test warning when incrementing non-counter."""
        engine = MetricsEngine()
        
        engine.register_metric("gauge_metric", "Test", "gauge")
        
        # Should log warning but not raise
        engine.increment("gauge_metric", value=1.0)
    
    def test_set_gauge_warning_for_non_gauge(self):
        """Test warning when setting non-gauge."""
        engine = MetricsEngine()
        
        engine.register_metric("counter_metric", "Test", "counter")
        
        # Should log warning but not raise
        engine.set_gauge("counter_metric", value=1.0)
    
    def test_observe_histogram_warning_for_non_histogram(self):
        """Test warning when observing non-histogram."""
        engine = MetricsEngine()
        
        engine.register_metric("gauge_metric", "Test", "gauge")
        
        # Should log warning but not raise
        engine.observe_histogram("gauge_metric", value=1.0)
    
    def test_get_metric_value_first_aggregation(self):
        """Test getting metric value with first aggregation."""
        engine = MetricsEngine()
        
        for i in range(5):
            engine.set_gauge("temperature", value=float(i * 10))
        
        value = engine.get_metric_value("temperature", aggregation="first")
        
        assert value == 0.0
    
    def test_get_metric_value_last_aggregation(self):
        """Test getting metric value with last aggregation."""
        engine = MetricsEngine()
        
        for i in range(5):
            engine.set_gauge("temperature", value=float(i * 10))
        
        value = engine.get_metric_value("temperature", aggregation="last")
        
        assert value == 40.0
    
    def test_export_prometheus_empty(self):
        """Test exporting empty metrics to Prometheus."""
        engine = MetricsEngine()
        
        export = engine.export_prometheus()
        
        assert export == ""
    
    def test_export_json_empty(self):
        """Test exporting empty metrics to JSON."""
        engine = MetricsEngine()
        
        export = engine.export_json()
        
        assert "metrics" in export
        assert "alerts" in export
    
    def test_cleanup_preserves_recent_data(self):
        """Test that cleanup preserves recent data."""
        engine = MetricsEngine()
        
        now = datetime.now(timezone.utc)
        
        # Add old data point
        old_point = MetricPoint(
            timestamp=(now - timedelta(hours=2)).isoformat(),
            value=10.0,
        )
        engine.register_metric("temperature", "Temperature", "gauge")
        engine._metrics["temperature"].points.append(old_point)
        
        # Add recent data point
        recent_point = MetricPoint(
            timestamp=now.isoformat(),
            value=25.0,
        )
        engine._metrics["temperature"].points.append(recent_point)
        
        # Clean up data older than 1 hour
        cutoff = (now - timedelta(hours=1)).isoformat()
        engine.cleanup_old_data(older_than=cutoff)
        
        metric = engine._metrics["temperature"]
        
        assert len(metric.points) == 1
        assert metric.points[0].value == 25.0
    
    def test_threshold_severity_default(self):
        """Test that threshold severity defaults to warning."""
        engine = MetricsEngine()
        
        threshold_id = engine.register_threshold("temperature", "gt", 25.0)
        
        thresholds = engine.get_thresholds()
        
        assert thresholds[0]["severity"] == "warning"
    
    def test_histogram_bucket_counts_reset_on_metric_reset(self):
        """Test that histogram bucket counts reset on metric reset."""
        engine = MetricsEngine()
        
        engine.register_metric("duration", "Duration", "histogram", buckets=[0.1, 0.5, 1.0])
        
        for value in [0.05, 0.3, 0.8]:
            engine.observe_histogram("duration", value)
        
        # Verify counts
        assert engine._metrics["duration"].bucket_counts[0.1] == 1
        
        # Reset
        engine.reset_metric("duration")
        
        # Verify counts reset
        assert engine._metrics["duration"].bucket_counts[0.1] == 0
    
    def test_multiple_alert_callbacks(self):
        """Test multiple alert callbacks."""
        engine = MetricsEngine()
        
        alerts1 = []
        alerts2 = []
        
        def callback1(alert):
            alerts1.append(alert)
        
        def callback2(alert):
            alerts2.append(alert)
        
        engine.register_alert_callback(callback1)
        engine.register_alert_callback(callback2)
        
        engine.register_threshold("temperature", "gt", 25.0)
        engine.set_gauge("temperature", value=30.0)
        
        assert len(alerts1) == 1
        assert len(alerts2) == 1
    
    def test_statistics_includes_threshold_count(self):
        """Test that statistics include threshold count."""
        engine = MetricsEngine()
        
        engine.register_threshold("temperature", "gt", 25.0)
        engine.register_threshold("humidity", "gt", 80.0)
        
        stats = engine.get_statistics()
        
        assert stats["total_thresholds"] == 2
    
    def test_statistics_includes_alert_count(self):
        """Test that statistics include alert count."""
        engine = MetricsEngine()
        
        engine.register_threshold("temperature", "gt", 25.0)
        
        engine.set_gauge("temperature", value=30.0)
        engine.set_gauge("temperature", value=35.0)
        
        stats = engine.get_statistics()
        
        assert stats["total_alerts"] == 2
    
    def test_metric_created_at_timestamp(self):
        """Test that metric has created_at timestamp."""
        engine = MetricsEngine()
        
        engine.register_metric("test", "Test metric", "gauge")
        
        metric = engine.get_metric("test")
        
        assert "created_at" in metric
        assert metric["created_at"] is not None
    
    def test_retention_hours_applied(self):
        """Test that retention hours are applied."""
        engine = MetricsEngine(retention_hours=12)
        
        # The retention is stored internally
        assert engine._retention == timedelta(hours=12)
