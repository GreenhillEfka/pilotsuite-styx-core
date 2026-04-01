"""Tests for Analytics Engine — Slice 52."""
import pytest
from copilot_core.analytics.engine import (
    AnalyticsEngine,
    MetricType,
    AggregationType,
    Event,
    Metric,
    MetricBucket,
    create_analytics_engine,
)
from datetime import datetime, timezone, timedelta
import json
import time


class TestAnalyticsEngine:
    """Test analytics engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_analytics_engine()
        assert engine is not None
    
    def test_create_engine_with_retention(self):
        """Test engine creation with retention days."""
        engine = create_analytics_engine(retention_days=90)
        assert engine._retention_days == 90
    
    def test_track_event(self):
        """Test tracking an event."""
        engine = AnalyticsEngine()
        
        event_id = engine.track_event("user.login")
        
        assert event_id is not None
        assert event_id.startswith("evt_")
    
    def test_track_event_with_properties(self):
        """Test tracking event with properties."""
        engine = AnalyticsEngine()
        
        event_id = engine.track_event(
            "user.login",
            properties={"method": "oauth", "provider": "google"},
        )
        
        events = engine.get_events(event_type="user.login", limit=1)
        
        assert len(events) == 1
        assert events[0].properties["method"] == "oauth"
        assert events[0].properties["provider"] == "google"
    
    def test_track_event_with_user_id(self):
        """Test tracking event with user ID."""
        engine = AnalyticsEngine()
        
        engine.track_event("user.action", user_id="user_123")
        
        events = engine.get_events(user_id="user_123", limit=10)
        
        assert len(events) == 1
        assert events[0].user_id == "user_123"
    
    def test_track_event_with_session_id(self):
        """Test tracking event with session ID."""
        engine = AnalyticsEngine()
        
        engine.track_event("page.view", session_id="sess_abc")
        
        events = engine.get_events(limit=10)
        
        assert events[0].session_id == "sess_abc"
    
    def test_get_events(self):
        """Test getting events."""
        engine = AnalyticsEngine()
        
        engine.track_event("event1")
        engine.track_event("event2")
        engine.track_event("event1")
        
        events = engine.get_events(limit=10)
        
        assert len(events) == 3
    
    def test_get_events_by_type(self):
        """Test getting events by type."""
        engine = AnalyticsEngine()
        
        engine.track_event("login")
        engine.track_event("logout")
        engine.track_event("login")
        
        events = engine.get_events(event_type="login", limit=10)
        
        assert len(events) == 2
    
    def test_get_events_by_user(self):
        """Test getting events by user ID."""
        engine = AnalyticsEngine()
        
        engine.track_event("action", user_id="user1")
        engine.track_event("action", user_id="user2")
        engine.track_event("action", user_id="user1")
        
        events = engine.get_events(user_id="user1", limit=10)
        
        assert len(events) == 2
    
    def test_get_events_with_limit(self):
        """Test getting events with limit."""
        engine = AnalyticsEngine()
        
        for i in range(100):
            engine.track_event(f"event_{i}")
        
        events = engine.get_events(limit=10)
        
        assert len(events) == 10
    
    def test_get_events_by_time_range(self):
        """Test getting events by time range."""
        engine = AnalyticsEngine()
        
        engine.track_event("early")
        
        time.sleep(0.1)
        mid_time = datetime.now(timezone.utc).isoformat()
        time.sleep(0.1)
        
        engine.track_event("late")
        
        events = engine.get_events(start_time=mid_time, limit=10)
        
        assert len(events) == 1
        assert events[0].event_type == "late"
    
    def test_increment_counter(self):
        """Test incrementing counter."""
        engine = AnalyticsEngine()
        
        engine.increment("requests")
        engine.increment("requests")
        engine.increment("requests", value=5)
        
        counter = engine.get_counter("requests")
        
        assert counter == 7
    
    def test_decrement_counter(self):
        """Test decrementing counter."""
        engine = AnalyticsEngine()
        
        engine.increment("balance", value=100)
        engine.decrement("balance", value=30)
        
        counter = engine.get_counter("balance")
        
        assert counter == 70
    
    def test_set_gauge(self):
        """Test setting gauge."""
        engine = AnalyticsEngine()
        
        engine.gauge("temperature", value=22.5)
        
        gauge = engine.get_gauge("temperature")
        
        assert gauge == 22.5
    
    def test_gauge_overwrites(self):
        """Test that gauge overwrites previous value."""
        engine = AnalyticsEngine()
        
        engine.gauge("cpu", value=50)
        engine.gauge("cpu", value=75)
        engine.gauge("cpu", value=25)
        
        gauge = engine.get_gauge("cpu")
        
        assert gauge == 25
    
    def test_record_timing(self):
        """Test recording timing metric."""
        engine = AnalyticsEngine()
        
        engine.timing("api.response", duration_ms=150)
        engine.timing("api.response", duration_ms=200)
        engine.timing("api.response", duration_ms=100)
        
        stats = engine.get_metric_stats("api.response")
        
        assert stats["count"] == 3
        assert stats["avg"] == 150
    
    def test_record_histogram(self):
        """Test recording histogram value."""
        engine = AnalyticsEngine()
        
        engine.histogram("response.size", value=1024)
        engine.histogram("response.size", value=2048)
        engine.histogram("response.size", value=512)
        
        stats = engine.get_metric_stats("response.size")
        
        assert stats["count"] == 3
        assert stats["min"] == 512
        assert stats["max"] == 2048
    
    def test_metric_with_tags(self):
        """Test metric with tags."""
        engine = AnalyticsEngine()
        
        engine.increment("requests", tags={"method": "GET", "endpoint": "/users"})
        engine.increment("requests", tags={"method": "POST", "endpoint": "/users"})
        engine.increment("requests", tags={"method": "GET", "endpoint": "/posts"})
        
        get_users = engine.get_counter("requests", tags={"method": "GET", "endpoint": "/users"})
        post_users = engine.get_counter("requests", tags={"method": "POST", "endpoint": "/users"})
        
        assert get_users == 1
        assert post_users == 1
    
    def test_get_metric_stats(self):
        """Test getting metric statistics."""
        engine = AnalyticsEngine()
        
        for i in range(10):
            engine.timing("latency", duration_ms=(i + 1) * 10)
        
        stats = engine.get_metric_stats("latency")
        
        assert stats["count"] == 10
        assert stats["min"] == 10
        assert stats["max"] == 100
        assert stats["avg"] == 55
    
    def test_get_metric_stats_empty(self):
        """Test getting stats for nonexistent metric."""
        engine = AnalyticsEngine()
        
        stats = engine.get_metric_stats("nonexistent")
        
        assert stats["count"] == 0
    
    def test_get_metric_stats_with_time_range(self):
        """Test getting stats with time range."""
        engine = AnalyticsEngine()
        
        engine.timing("metric", duration_ms=10)
        
        time.sleep(0.1)
        mid_time = datetime.now(timezone.utc).isoformat()
        time.sleep(0.1)
        
        engine.timing("metric", duration_ms=20)
        
        stats = engine.get_metric_stats("metric", start_time=mid_time)
        
        assert stats["count"] == 1
        assert stats["min"] == 20
    
    def test_get_metric_stats_with_tags(self):
        """Test getting stats with tag filter."""
        engine = AnalyticsEngine()
        
        engine.timing("request", duration_ms=10, tags={"method": "GET"})
        engine.timing("request", duration_ms=20, tags={"method": "POST"})
        engine.timing("request", duration_ms=30, tags={"method": "GET"})
        
        stats = engine.get_metric_stats("request", tags={"method": "GET"})
        
        assert stats["count"] == 2
        assert stats["avg"] == 20
    
    def test_metric_percentiles(self):
        """Test metric percentile calculations."""
        engine = AnalyticsEngine()
        
        # Record 100 values
        for i in range(1, 101):
            engine.timing("perf", duration_ms=i)
        
        stats = engine.get_metric_stats("perf")
        
        assert stats["p50"] == 50
        assert stats["p90"] == 90
        assert stats["p99"] == 99
    
    def test_get_buckets(self):
        """Test getting metric buckets."""
        engine = AnalyticsEngine()
        
        for i in range(10):
            engine.timing("metric", duration_ms=i * 10)
        
        buckets = engine.get_buckets("metric")
        
        # Should have at least 1 bucket (1-minute buckets)
        assert len(buckets) >= 1
    
    def test_query_with_aggregation(self):
        """Test querying with aggregation."""
        engine = AnalyticsEngine()
        
        for i in range(10):
            engine.timing("latency", duration_ms=(i + 1) * 10)
        
        now = datetime.now(timezone.utc)
        start = (now - timedelta(minutes=5)).isoformat()
        end = (now + timedelta(minutes=5)).isoformat()
        
        results = engine.query(
            "latency",
            AggregationType.AVG,
            start_time=start,
            end_time=end,
        )
        
        assert len(results) >= 1
        assert results[0]["value"] == 55
    
    def test_query_sum_aggregation(self):
        """Test query with SUM aggregation."""
        engine = AnalyticsEngine()
        
        for i in range(5):
            engine.increment("requests")
        
        now = datetime.now(timezone.utc)
        start = (now - timedelta(minutes=5)).isoformat()
        end = (now + timedelta(minutes=5)).isoformat()
        
        results = engine.query(
            "requests",
            AggregationType.SUM,
            start_time=start,
            end_time=end,
        )
        
        assert len(results) >= 1
        assert results[0]["value"] == 5
    
    def test_query_count_aggregation(self):
        """Test query with COUNT aggregation."""
        engine = AnalyticsEngine()
        
        for i in range(7):
            engine.timing("metric", duration_ms=10)
        
        now = datetime.now(timezone.utc)
        start = (now - timedelta(minutes=5)).isoformat()
        end = (now + timedelta(minutes=5)).isoformat()
        
        results = engine.query(
            "metric",
            AggregationType.COUNT,
            start_time=start,
            end_time=end,
        )
        
        assert len(results) >= 1
        assert results[0]["value"] == 7
    
    def test_query_min_aggregation(self):
        """Test query with MIN aggregation."""
        engine = AnalyticsEngine()
        
        engine.timing("metric", duration_ms=100)
        engine.timing("metric", duration_ms=50)
        engine.timing("metric", duration_ms=75)
        
        now = datetime.now(timezone.utc)
        start = (now - timedelta(minutes=5)).isoformat()
        end = (now + timedelta(minutes=5)).isoformat()
        
        results = engine.query(
            "metric",
            AggregationType.MIN,
            start_time=start,
            end_time=end,
        )
        
        assert len(results) >= 1
        assert results[0]["value"] == 50
    
    def test_query_max_aggregation(self):
        """Test query with MAX aggregation."""
        engine = AnalyticsEngine()
        
        engine.timing("metric", duration_ms=100)
        engine.timing("metric", duration_ms=50)
        engine.timing("metric", duration_ms=75)
        
        now = datetime.now(timezone.utc)
        start = (now - timedelta(minutes=5)).isoformat()
        end = (now + timedelta(minutes=5)).isoformat()
        
        results = engine.query(
            "metric",
            AggregationType.MAX,
            start_time=start,
            end_time=end,
        )
        
        assert len(results) >= 1
        assert results[0]["value"] == 100
    
    def test_query_p50_aggregation(self):
        """Test query with P50 aggregation."""
        engine = AnalyticsEngine()
        
        for i in range(1, 101):
            engine.timing("metric", duration_ms=i)
        
        now = datetime.now(timezone.utc)
        start = (now - timedelta(minutes=5)).isoformat()
        end = (now + timedelta(minutes=5)).isoformat()
        
        results = engine.query(
            "metric",
            AggregationType.P50,
            start_time=start,
            end_time=end,
        )
        
        assert len(results) >= 1
        assert results[0]["value"] == 50
    
    def test_on_event_handler(self):
        """Test event handler registration."""
        engine = AnalyticsEngine()
        
        received = []
        
        def handler(event):
            received.append(event.event_type)
        
        engine.on_event(handler)
        
        engine.track_event("test_event")
        
        time.sleep(0.1)
        
        assert "test_event" in received
    
    def test_multiple_event_handlers(self):
        """Test multiple event handlers."""
        engine = AnalyticsEngine()
        
        received1 = []
        received2 = []
        
        engine.on_event(lambda e: received1.append(e.event_type))
        engine.on_event(lambda e: received2.append(e.event_type))
        
        engine.track_event("broadcast")
        
        time.sleep(0.1)
        
        assert "broadcast" in received1
        assert "broadcast" in received2
    
    def test_export_events_json(self):
        """Test exporting events as JSON."""
        engine = AnalyticsEngine()
        
        engine.track_event("event1", user_id="user1")
        engine.track_event("event2", user_id="user2")
        
        export = engine.export_events(format="json")
        
        data = json.loads(export)
        
        assert len(data) == 2
        assert data[0]["event_type"] == "event1"
    
    def test_export_events_csv(self):
        """Test exporting events as CSV."""
        engine = AnalyticsEngine()
        
        engine.track_event("event1", user_id="user1")
        engine.track_event("event2", user_id="user2")
        
        export = engine.export_events(format="csv")
        
        lines = export.split("\n")
        
        assert len(lines) == 3  # Header + 2 events
        assert "event_id,event_type,timestamp" in lines[0]
    
    def test_export_metrics_json(self):
        """Test exporting metrics as JSON."""
        engine = AnalyticsEngine()
        
        engine.timing("latency", duration_ms=100)
        engine.timing("latency", duration_ms=200)
        
        export = engine.export_metrics(format="json")
        
        data = json.loads(export)
        
        assert len(data) == 2
        assert data[0]["name"] == "latency"
    
    def test_export_metrics_by_name(self):
        """Test exporting specific metric."""
        engine = AnalyticsEngine()
        
        engine.timing("latency", duration_ms=100)
        engine.increment("requests")
        
        export = engine.export_metrics(name="latency", format="json")
        
        data = json.loads(export)
        
        assert len(data) == 1
        assert data[0]["name"] == "latency"
    
    def test_export_metrics_csv(self):
        """Test exporting metrics as CSV."""
        engine = AnalyticsEngine()
        
        engine.timing("metric", duration_ms=100)
        
        export = engine.export_metrics(format="csv")
        
        lines = export.split("\n")
        
        assert len(lines) == 2  # Header + 1 metric
        assert "metric_id,name,type,value" in lines[0]
    
    def test_clear_events(self):
        """Test clearing all events."""
        engine = AnalyticsEngine()
        
        for i in range(10):
            engine.track_event(f"event_{i}")
        
        count = engine.clear_events()
        
        assert count == 10
        assert len(engine.get_events(limit=100)) == 0
    
    def test_clear_events_older_than(self):
        """Test clearing events older than."""
        engine = AnalyticsEngine()
        
        engine.track_event("old")
        
        time.sleep(0.1)
        engine.track_event("new")
        
        # Manually adjust timestamp for testing
        if engine._events:
            engine._events[0].timestamp = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        
        count = engine.clear_events(older_than_days=1)
        
        # Old event should be cleared
        events = engine.get_events(limit=10)
        assert len(events) == 1
        assert events[0].event_type == "new"
    
    def test_clear_metrics(self):
        """Test clearing all metrics."""
        engine = AnalyticsEngine()
        
        for i in range(20):
            engine.timing("metric", duration_ms=i * 10)
        
        count = engine.clear_metrics()
        
        assert count == 20
        
        stats = engine.get_metric_stats("metric")
        assert stats["count"] == 0
    
    def test_apply_retention(self):
        """Test applying retention policy."""
        engine = AnalyticsEngine(retention_days=1)
        
        engine.track_event("event1")
        engine.timing("metric", duration_ms=100)
        
        # Adjust timestamps to be old
        if engine._events:
            old_time = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
            engine._events[0].timestamp = old_time
        
        if engine._metrics:
            for metrics in engine._metrics.values():
                for m in metrics:
                    m.timestamp = old_time
        
        events_cleared, metrics_cleared = engine.apply_retention()
        
        assert events_cleared == 1
        assert metrics_cleared == 1
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = AnalyticsEngine()
        
        engine.track_event("event1")
        engine.track_event("event2")
        engine.increment("counter")
        engine.gauge("gauge", value=50)
        
        stats = engine.get_statistics()
        
        assert stats["total_events"] == 2
        assert stats["total_metrics"] == 2
        assert stats["total_events_stored"] == 2
        assert stats["retention_days"] == 30
    
    def test_statistics_events_by_type(self):
        """Test statistics by event type."""
        engine = AnalyticsEngine()
        
        engine.track_event("login")
        engine.track_event("login")
        engine.track_event("logout")
        
        stats = engine.get_statistics()
        
        assert stats["events_by_type"]["login"] == 2
        assert stats["events_by_type"]["logout"] == 1
    
    def test_statistics_metrics_by_name(self):
        """Test statistics by metric name."""
        engine = AnalyticsEngine()
        
        engine.timing("latency", duration_ms=10)
        engine.timing("latency", duration_ms=20)
        engine.increment("requests")
        
        stats = engine.get_statistics()
        
        assert stats["metrics_by_name"]["latency"] == 2
        assert stats["metrics_by_name"]["requests"] == 1
    
    def test_event_to_dict(self):
        """Test event serialization."""
        event = Event(
            event_id="evt_test",
            event_type="test.event",
            timestamp="2025-01-01T00:00:00Z",
            properties={"key": "value"},
            user_id="user_123",
            session_id="sess_456",
        )
        
        d = event.to_dict()
        
        assert d["event_id"] == "evt_test"
        assert d["event_type"] == "test.event"
        assert d["properties"]["key"] == "value"
    
    def test_metric_to_dict(self):
        """Test metric serialization."""
        metric = Metric(
            metric_id="met_test",
            name="test.metric",
            metric_type=MetricType.GAUGE,
            value=42.5,
            timestamp="2025-01-01T00:00:00Z",
            tags={"env": "prod"},
        )
        
        d = metric.to_dict()
        
        assert d["metric_id"] == "met_test"
        assert d["name"] == "test.metric"
        assert d["metric_type"] == "gauge"
        assert d["value"] == 42.5
    
    def test_metric_bucket_add(self):
        """Test metric bucket add."""
        bucket = MetricBucket(
            name="test",
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-01T00:01:00Z",
        )
        
        bucket.add(10)
        bucket.add(20)
        bucket.add(30)
        
        assert bucket.count == 3
        assert bucket.sum == 60
        assert bucket.min == 10
        assert bucket.max == 30
    
    def test_metric_bucket_avg(self):
        """Test metric bucket average."""
        bucket = MetricBucket(
            name="test",
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-01T00:01:00Z",
        )
        
        bucket.add(10)
        bucket.add(20)
        bucket.add(30)
        
        assert bucket.avg() == 20
    
    def test_metric_bucket_avg_empty(self):
        """Test metric bucket average when empty."""
        bucket = MetricBucket(
            name="test",
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-01T00:01:00Z",
        )
        
        assert bucket.avg() is None
    
    def test_metric_bucket_percentile(self):
        """Test metric bucket percentile."""
        bucket = MetricBucket(
            name="test",
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-01T00:01:00Z",
        )
        
        for i in range(1, 101):
            bucket.add(i)
        
        assert bucket.percentile(50) == 50
        assert bucket.percentile(90) == 90
        assert bucket.percentile(99) == 99
    
    def test_metric_bucket_percentile_empty(self):
        """Test metric bucket percentile when empty."""
        bucket = MetricBucket(
            name="test",
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-01T00:01:00Z",
        )
        
        assert bucket.percentile(50) is None
    
    def test_metric_bucket_to_dict(self):
        """Test metric bucket serialization."""
        bucket = MetricBucket(
            name="test",
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-01T00:01:00Z",
        )
        
        bucket.add(10)
        bucket.add(20)
        
        d = bucket.to_dict()
        
        assert d["name"] == "test"
        assert d["count"] == 2
        assert d["avg"] == 15
    
    def test_metric_type_enum_values(self):
        """Test metric type enum values."""
        assert MetricType.COUNTER.value == "counter"
        assert MetricType.GAUGE.value == "gauge"
        assert MetricType.HISTOGRAM.value == "histogram"
        assert MetricType.TIMER.value == "timer"
    
    def test_aggregation_type_enum_values(self):
        """Test aggregation type enum values."""
        assert AggregationType.SUM.value == "sum"
        assert AggregationType.AVG.value == "avg"
        assert AggregationType.MIN.value == "min"
        assert AggregationType.MAX.value == "max"
        assert AggregationType.COUNT.value == "count"
        assert AggregationType.P50.value == "p50"
        assert AggregationType.P90.value == "p90"
        assert AggregationType.P99.value == "p99"
    
    def test_counter_with_tags_unique(self):
        """Test that counters with different tags are unique."""
        engine = AnalyticsEngine()
        
        engine.increment("requests", tags={"method": "GET"})
        engine.increment("requests", tags={"method": "POST"})
        engine.increment("requests", tags={"method": "GET"})
        
        get_count = engine.get_counter("requests", tags={"method": "GET"})
        post_count = engine.get_counter("requests", tags={"method": "POST"})
        
        assert get_count == 2
        assert post_count == 1
    
    def test_gauge_with_tags(self):
        """Test gauge with tags."""
        engine = AnalyticsEngine()
        
        engine.gauge("cpu", value=50, tags={"host": "server1"})
        engine.gauge("cpu", value=75, tags={"host": "server2"})
        
        server1 = engine.get_gauge("cpu", tags={"host": "server1"})
        server2 = engine.get_gauge("cpu", tags={"host": "server2"})
        
        assert server1 == 50
        assert server2 == 75
    
    def test_timing_stores_metric(self):
        """Test that timing stores metric data."""
        engine = AnalyticsEngine()
        
        engine.timing("api.latency", duration_ms=250)
        
        metrics = engine._metrics.get("api.latency")
        
        assert metrics is not None
        assert len(metrics) == 1
        assert metrics[0].value == 250
    
    def test_histogram_stores_metric(self):
        """Test that histogram stores metric data."""
        engine = AnalyticsEngine()
        
        engine.histogram("response.size", value=4096)
        
        metrics = engine._metrics.get("response.size")
        
        assert metrics is not None
        assert len(metrics) == 1
    
    def test_event_id_unique(self):
        """Test that event IDs are unique."""
        engine = AnalyticsEngine()
        
        ids = set()
        for i in range(100):
            event_id = engine.track_event(f"event_{i}")
            ids.add(event_id)
        
        assert len(ids) == 100
    
    def test_metric_id_unique(self):
        """Test that metric IDs are unique."""
        engine = AnalyticsEngine()
        
        ids = set()
        for i in range(100):
            engine.timing("metric", duration_ms=i)
            
            # Get the last metric ID
            metrics = engine._metrics["metric"]
            ids.add(metrics[-1].metric_id)
        
        assert len(ids) == 100
    
    def test_bucket_time_range(self):
        """Test that buckets have correct time range."""
        engine = AnalyticsEngine()
        
        engine.timing("metric", duration_ms=100)
        
        buckets = engine.get_buckets("metric")
        
        assert len(buckets) >= 1
        
        bucket = buckets[0]
        
        # End time should be 1 minute after start
        start = datetime.fromisoformat(bucket.start_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(bucket.end_time.replace('Z', '+00:00'))
        
        assert (end - start).total_seconds() == 60
    
    def test_query_empty_result(self):
        """Test query with no matching data."""
        engine = AnalyticsEngine()
        
        now = datetime.now(timezone.utc)
        start = (now - timedelta(hours=1)).isoformat()
        end = now.isoformat()
        
        results = engine.query(
            "nonexistent",
            AggregationType.AVG,
            start_time=start,
            end_time=end,
        )
        
        assert results == []
    
    def test_statistics_total_counters(self):
        """Test that statistics track total counters."""
        engine = AnalyticsEngine()
        
        engine.increment("counter1")
        engine.increment("counter2")
        engine.increment("counter1")
        
        stats = engine.get_statistics()
        
        assert stats["total_counters"] == 2
    
    def test_statistics_total_gauges(self):
        """Test that statistics track total gauges."""
        engine = AnalyticsEngine()
        
        engine.gauge("gauge1", value=10)
        engine.gauge("gauge2", value=20)
        engine.gauge("gauge1", value=15)
        
        stats = engine.get_statistics()
        
        assert stats["total_gauges"] == 2
    
    def test_statistics_total_buckets(self):
        """Test that statistics track total buckets."""
        engine = AnalyticsEngine()
        
        engine.timing("metric1", duration_ms=10)
        engine.timing("metric2", duration_ms=20)
        
        stats = engine.get_statistics()
        
        assert stats["total_buckets"] >= 2
    
    def test_get_gauge_nonexistent(self):
        """Test getting nonexistent gauge."""
        engine = AnalyticsEngine()
        
        gauge = engine.get_gauge("nonexistent")
        
        assert gauge is None
    
    def test_event_handler_exception_handled(self):
        """Test that event handler exceptions are handled."""
        engine = AnalyticsEngine()
        
        def failing_handler(event):
            raise ValueError("Handler failed")
        
        def working_handler(event):
            working_handler.called = True
        
        working_handler.called = False
        
        engine.on_event(failing_handler)
        engine.on_event(working_handler)
        
        # Should not raise
        engine.track_event("test")
        
        time.sleep(0.1)
        
        assert working_handler.called is True
    
    def test_clear_metrics_preserves_recent(self):
        """Test that clear with retention preserves recent metrics."""
        engine = AnalyticsEngine()
        
        # Add old metric
        engine.timing("metric", duration_ms=100)
        engine._metrics["metric"][0].timestamp = (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()
        
        # Add recent metric
        engine.timing("metric", duration_ms=200)
        
        count = engine.clear_metrics(older_than_days=1)
        
        assert count == 1
        
        stats = engine.get_metric_stats("metric")
        assert stats["count"] == 1
        assert stats["max"] == 200
    
    def test_query_p99_aggregation(self):
        """Test query with P99 aggregation."""
        engine = AnalyticsEngine()
        
        for i in range(1, 101):
            engine.timing("metric", duration_ms=i)
        
        now = datetime.now(timezone.utc)
        start = (now - timedelta(minutes=5)).isoformat()
        end = (now + timedelta(minutes=5)).isoformat()
        
        results = engine.query(
            "metric",
            AggregationType.P99,
            start_time=start,
            end_time=end,
        )
        
        assert len(results) >= 1
        assert results[0]["value"] == 99
    
    def test_bucket_min_max_single_value(self):
        """Test bucket min/max with single value."""
        bucket = MetricBucket(
            name="test",
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-01T00:01:00Z",
        )
        
        bucket.add(42)
        
        assert bucket.min == 42
        assert bucket.max == 42
    
    def test_track_event_all_fields(self):
        """Test tracking event with all fields."""
        engine = AnalyticsEngine()
        
        event_id = engine.track_event(
            "user.purchase",
            properties={"product": "widget", "price": 29.99},
            user_id="user_123",
            session_id="sess_456",
        )
        
        events = engine.get_events(event_type="user.purchase", limit=1)
        
        assert len(events) == 1
        assert events[0].event_id == event_id
        assert events[0].properties["product"] == "widget"
        assert events[0].properties["price"] == 29.99
        assert events[0].user_id == "user_123"
        assert events[0].session_id == "sess_456"
    
    def test_increment_negative_value(self):
        """Test incrementing with negative value."""
        engine = AnalyticsEngine()
        
        engine.increment("counter", value=-5)
        
        counter = engine.get_counter("counter")
        
        assert counter == -5
    
    def test_decrement_negative_value(self):
        """Test decrementing with negative value (adds)."""
        engine = AnalyticsEngine()
        
        engine.decrement("counter", value=-10)
        
        counter = engine.get_counter("counter")
        
        assert counter == 10
    
    def test_gauge_float_value(self):
        """Test gauge with float value."""
        engine = AnalyticsEngine()
        
        engine.gauge("temperature", value=23.456)
        
        gauge = engine.get_gauge("temperature")
        
        assert gauge == 23.456
    
    def test_timing_zero_duration(self):
        """Test timing with zero duration."""
        engine = AnalyticsEngine()
        
        engine.timing("instant", duration_ms=0)
        
        stats = engine.get_metric_stats("instant")
        
        assert stats["count"] == 1
        assert stats["min"] == 0
        assert stats["max"] == 0
    
    def test_histogram_negative_value(self):
        """Test histogram with negative value."""
        engine = AnalyticsEngine()
        
        engine.histogram("temperature", value=-10)
        engine.histogram("temperature", value=5)
        
        stats = engine.get_metric_stats("temperature")
        
        assert stats["min"] == -10
        assert stats["max"] == 5
    
    def test_query_with_empty_buckets(self):
        """Test query when no buckets exist."""
        engine = AnalyticsEngine()
        
        now = datetime.now(timezone.utc)
        start = (now - timedelta(hours=1)).isoformat()
        end = now.isoformat()
        
        results = engine.query(
            "nonexistent",
            AggregationType.SUM,
            start_time=start,
            end_time=end,
        )
        
        assert results == []
    
    def test_export_empty_events(self):
        """Test exporting when no events."""
        engine = AnalyticsEngine()
        
        export = engine.export_events(format="json")
        
        data = json.loads(export)
        
        assert data == []
    
    def test_export_empty_metrics(self):
        """Test exporting when no metrics."""
        engine = AnalyticsEngine()
        
        export = engine.export_metrics(format="json")
        
        data = json.loads(export)
        
        assert data == []
    
    def test_clear_empty_events(self):
        """Test clearing when no events."""
        engine = AnalyticsEngine()
        
        count = engine.clear_events()
        
        assert count == 0
    
    def test_clear_empty_metrics(self):
        """Test clearing when no metrics."""
        engine = AnalyticsEngine()
        
        count = engine.clear_metrics()
        
        assert count == 0
    
    def test_statistics_initial_values(self):
        """Test statistics initial values."""
        engine = AnalyticsEngine()
        
        stats = engine.get_statistics()
        
        assert stats["total_events"] == 0
        assert stats["total_metrics"] == 0
        assert stats["total_events_stored"] == 0
        assert stats["total_metrics_stored"] == 0
