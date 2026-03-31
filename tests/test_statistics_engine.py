"""Tests for Statistics & Analytics Engine — Slice 21."""
import pytest
from copilot_core.statistics.engine import (
    StatisticsEngine,
    AggregationType,
    TrendDirection,
    create_statistics_engine,
)
from datetime import datetime, timezone, timedelta


class TestStatisticsEngine:
    """Test statistics engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_statistics_engine()
        assert engine is not None
    
    def test_define_metric(self):
        """Test metric definition."""
        engine = StatisticsEngine()
        
        metric_id = engine.define_metric(
            metric_id="energy_total",
            name="Total Energy",
            description="Total energy consumption",
            unit="kWh",
            aggregation=AggregationType.SUM,
            source_entities=["sensor.energy_1", "sensor.energy_2"],
        )
        
        assert metric_id == "energy_total"
        assert metric_id in engine._metrics
        assert engine._metrics[metric_id].name == "Total Energy"
    
    def test_add_data_point(self):
        """Test adding data points."""
        engine = StatisticsEngine()
        engine.define_metric("test_metric", "Test", "Desc", "units", AggregationType.AVG, [])
        
        engine.add_data_point("test_metric", 10.0)
        engine.add_data_point("test_metric", 20.0)
        engine.add_data_point("test_metric", 30.0)
        
        assert len(engine._data_points["test_metric"]) == 3
    
    def test_get_statistics_avg(self):
        """Test statistics calculation - average."""
        engine = StatisticsEngine()
        engine.define_metric("test_metric", "Test", "Desc", "units", AggregationType.AVG, [])
        
        for value in [10.0, 20.0, 30.0, 40.0, 50.0]:
            engine.add_data_point("test_metric", value)
        
        stats = engine.get_statistics("test_metric", hours=24)
        
        assert stats["count"] == 5
        assert stats["avg"] == 30.0
        assert stats["min"] == 10.0
        assert stats["max"] == 50.0
        assert stats["sum"] == 150.0
    
    def test_get_statistics_median(self):
        """Test statistics calculation - median."""
        engine = StatisticsEngine()
        engine.define_metric("test_metric", "Test", "Desc", "units", AggregationType.MEDIAN, [])
        
        for value in [1.0, 2.0, 3.0, 4.0, 5.0]:
            engine.add_data_point("test_metric", value)
        
        stats = engine.get_statistics("test_metric", hours=24)
        
        assert stats["median"] == 3.0
    
    def test_get_statistics_median_even(self):
        """Test median with even number of values."""
        engine = StatisticsEngine()
        engine.define_metric("test_metric", "Test", "Desc", "units", AggregationType.MEDIAN, [])
        
        for value in [1.0, 2.0, 3.0, 4.0]:
            engine.add_data_point("test_metric", value)
        
        stats = engine.get_statistics("test_metric", hours=24)
        
        assert stats["median"] == 2.5
    
    def test_get_statistics_stddev(self):
        """Test statistics calculation - standard deviation."""
        engine = StatisticsEngine()
        engine.define_metric("test_metric", "Test", "Desc", "units", AggregationType.AVG, [])
        
        # Values with known stddev
        for value in [2.0, 4.0, 4.0, 4.0, 5.0, 5.0, 7.0, 9.0]:
            engine.add_data_point("test_metric", value)
        
        stats = engine.get_statistics("test_metric", hours=24)
        
        # Stddev should be > 0
        assert stats["stddev"] > 0
    
    def test_get_trend_increasing(self):
        """Test trend detection - increasing."""
        engine = StatisticsEngine()
        engine.define_metric("test_metric", "Test", "Desc", "units", AggregationType.AVG, [])
        
        # Add increasing values
        for i in range(10):
            engine.add_data_point("test_metric", float(i * 10))
        
        trend = engine.get_trend("test_metric", hours=24)
        
        assert trend.direction == TrendDirection.INCREASING
        assert trend.slope > 0
    
    def test_get_trend_decreasing(self):
        """Test trend detection - decreasing."""
        engine = StatisticsEngine()
        engine.define_metric("test_metric", "Test", "Desc", "units", AggregationType.AVG, [])
        
        # Add decreasing values
        for i in range(10):
            engine.add_data_point("test_metric", float(100 - i * 10))
        
        trend = engine.get_trend("test_metric", hours=24)
        
        assert trend.direction == TrendDirection.DECREASING
        assert trend.slope < 0
    
    def test_get_trend_stable(self):
        """Test trend detection - stable."""
        engine = StatisticsEngine()
        engine.define_metric("test_metric", "Test", "Desc", "units", AggregationType.AVG, [])
        
        # Add stable values (with small variance)
        for i in range(10):
            engine.add_data_point("test_metric", 50.0 + (i % 2) * 0.1)
        
        trend = engine.get_trend("test_metric", hours=24)
        
        assert trend.direction == TrendDirection.STABLE
    
    def test_get_hourly_breakdown(self):
        """Test hourly breakdown."""
        engine = StatisticsEngine()
        engine.define_metric("test_metric", "Test", "Desc", "units", AggregationType.AVG, [])
        
        now = datetime.now(timezone.utc)
        
        # Add points for different hours
        for hour_offset in range(5):
            for minute in range(0, 60, 15):
                timestamp = (now - timedelta(hours=hour_offset)).replace(minute=minute).isoformat()
                engine._data_points["test_metric"].append(
                    type('DataPoint', (), {
                        "timestamp": timestamp,
                        "value": float(hour_offset * 10 + minute),
                        "entity_id": None,
                        "zone_id": None,
                        "module_id": None,
                        "metadata": {},
                    })()
                )
        
        breakdown = engine.get_hourly_breakdown("test_metric", hours=24)
        
        assert len(breakdown) >= 1
        assert "hour" in breakdown[0]
        assert "avg" in breakdown[0]
    
    def test_compare_periods(self):
        """Test period comparison."""
        engine = StatisticsEngine()
        engine.define_metric("test_metric", "Test", "Desc", "units", AggregationType.AVG, [])
        
        now = datetime.now(timezone.utc)
        
        # Add current period values (higher)
        for i in range(10):
            timestamp = (now - timedelta(hours=i)).isoformat()
            engine._data_points["test_metric"].append(
                type('DataPoint', (), {
                    "timestamp": timestamp,
                    "value": 100.0,
                    "entity_id": None,
                    "zone_id": None,
                    "module_id": None,
                    "metadata": {},
                })()
            )
        
        # Add previous period values (lower)
        for i in range(10, 20):
            timestamp = (now - timedelta(hours=i)).isoformat()
            engine._data_points["test_metric"].append(
                type('DataPoint', (), {
                    "timestamp": timestamp,
                    "value": 50.0,
                    "entity_id": None,
                    "zone_id": None,
                    "module_id": None,
                    "metadata": {},
                })()
            )
        
        comparison = engine.compare_periods("test_metric", hours_current=10, hours_previous=10)
        
        assert comparison["current_avg"] == 100.0
        assert comparison["previous_avg"] == 50.0
        assert comparison["change_absolute"] == 50.0
        assert comparison["change_percent"] == 100.0
        assert comparison["trend"] == "up"
    
    def test_get_all_metrics(self):
        """Test getting all metrics."""
        engine = StatisticsEngine()
        
        engine.define_metric("metric_1", "Metric 1", "Desc 1", "units", AggregationType.AVG, [])
        engine.define_metric("metric_2", "Metric 2", "Desc 2", "units", AggregationType.SUM, [])
        
        metrics = engine.get_all_metrics()
        
        assert len(metrics) == 2
    
    def test_data_point_trimming(self):
        """Test that data points are trimmed to max."""
        engine = StatisticsEngine()
        engine._max_points_per_metric = 100
        engine.define_metric("test_metric", "Test", "Desc", "units", AggregationType.AVG, [])
        
        # Add 150 points
        for i in range(150):
            engine.add_data_point("test_metric", float(i))
        
        assert len(engine._data_points["test_metric"]) == 100
    
    def test_statistics_cache(self):
        """Test statistics caching."""
        engine = StatisticsEngine()
        engine.define_metric("test_metric", "Test", "Desc", "units", AggregationType.AVG, [])
        
        engine.add_data_point("test_metric", 10.0)
        
        # First call
        stats1 = engine.get_statistics("test_metric", hours=24)
        
        # Second call (should use cache)
        stats2 = engine.get_statistics("test_metric", hours=24)
        
        assert stats1["avg"] == stats2["avg"]
        assert "computed_at" in stats1
    
    def test_empty_statistics(self):
        """Test statistics for empty metric."""
        engine = StatisticsEngine()
        engine.define_metric("empty_metric", "Empty", "Desc", "units", AggregationType.AVG, [])
        
        stats = engine.get_statistics("empty_metric", hours=24)
        
        assert stats["count"] == 0
        assert stats["avg"] is None
        assert stats["min"] is None
        assert stats["max"] is None
    
    def test_trend_with_insufficient_data(self):
        """Test trend with insufficient data."""
        engine = StatisticsEngine()
        engine.define_metric("test_metric", "Test", "Desc", "units", AggregationType.AVG, [])
        
        # Add only 2 points (need at least 3 for trend)
        engine.add_data_point("test_metric", 10.0)
        engine.add_data_point("test_metric", 20.0)
        
        trend = engine.get_trend("test_metric", hours=24)
        
        assert trend.direction == TrendDirection.STABLE
        assert trend.confidence == 0.0
    
    def test_anomaly_detection(self):
        """Test anomaly detection."""
        engine = StatisticsEngine()
        engine.define_metric("test_metric", "Test", "Desc", "units", AggregationType.AVG, [])
        
        # Add normal values
        for i in range(20):
            engine.add_data_point("test_metric", 100.0)
        
        # Add anomaly
        engine.add_data_point("test_metric", 500.0)
        
        trend = engine.get_trend("test_metric", hours=24)
        
        assert trend.anomalies_detected >= 1
    
    def test_metric_to_dict(self):
        """Test metric definition serialization."""
        from copilot_core.statistics.engine import MetricDefinition
        
        metric = MetricDefinition(
            metric_id="test_metric",
            name="Test Metric",
            description="Test description",
            unit="kWh",
            aggregation=AggregationType.SUM,
            source_entities=["sensor.a", "sensor.b"],
        )
        
        d = metric.to_dict()
        
        assert d["metric_id"] == "test_metric"
        assert d["name"] == "Test Metric"
        assert d["unit"] == "kWh"
        assert d["aggregation"] == "sum"
        assert d["source_entities"] == ["sensor.a", "sensor.b"]
    
    def test_trend_analysis_to_dict(self):
        """Test trend analysis serialization."""
        from copilot_core.statistics.engine import TrendAnalysis
        
        trend = TrendAnalysis(
            metric_id="test_metric",
            direction=TrendDirection.INCREASING,
            slope=0.5,
            confidence=0.8,
            r_squared=0.9,
            forecast_1h=105.0,
            forecast_24h=120.0,
            anomalies_detected=2,
        )
        
        d = trend.to_dict()
        
        assert d["metric_id"] == "test_metric"
        assert d["direction"] == "increasing"
        assert d["slope"] == 0.5
        assert d["confidence"] == 0.8
        assert d["forecast_1h"] == 105.0
    
    def test_data_point_to_dict(self):
        """Test data point serialization."""
        from copilot_core.statistics.engine import DataPoint
        
        point = DataPoint(
            timestamp="2026-03-31T12:00:00Z",
            value=42.5,
            entity_id="sensor.test",
            zone_id="zone_test",
            module_id="module_test",
            metadata={"source": "test"},
        )
        
        d = point.to_dict()
        
        assert d["timestamp"] == "2026-03-31T12:00:00Z"
        assert d["value"] == 42.5
        assert d["entity_id"] == "sensor.test"
        assert d["metadata"] == {"source": "test"}
    
    def test_linear_regression_calculation(self):
        """Test linear regression calculation."""
        engine = StatisticsEngine()
        
        # Perfect linear relationship: y = 2x + 1
        x = [1.0, 2.0, 3.0, 4.0, 5.0]
        y = [3.0, 5.0, 7.0, 9.0, 11.0]
        
        slope, intercept, r_squared = engine._linear_regression(x, y)
        
        assert abs(slope - 2.0) < 0.01
        assert abs(intercept - 1.0) < 0.01
        assert r_squared == 1.0  # Perfect fit
    
    def test_compare_periods_no_data(self):
        """Test period comparison with no data."""
        engine = StatisticsEngine()
        engine.define_metric("empty_metric", "Empty", "Desc", "units", AggregationType.AVG, [])
        
        comparison = engine.compare_periods("empty_metric", hours_current=24, hours_previous=24)
        
        assert comparison["current_avg"] is None
        assert comparison["previous_avg"] is None
