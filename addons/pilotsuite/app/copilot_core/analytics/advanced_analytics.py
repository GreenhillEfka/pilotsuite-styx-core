"""PilotSuite Advanced Analytics — Metrics, Dashboards, and Insights."""
from __future__ import annotations

import logging
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, field
from enum import Enum
from collections import defaultdict

logger = logging.getLogger(__name__)


# =============================================================================
# METRIC TYPES
# =============================================================================

class MetricType(Enum):
    """Types of metrics."""
    GAUGE = "gauge"  # Current value (e.g., temperature)
    COUNTER = "counter"  # Cumulative count (e.g., requests)
    HISTOGRAM = "histogram"  # Distribution (e.g., response times)
    SUMMARY = "summary"  # Aggregated stats


@dataclass
class MetricPoint:
    """Single metric data point."""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class Metric:
    """Metric definition."""
    name: str
    type: MetricType
    description: str
    unit: str = ""
    points: List[MetricPoint] = field(default_factory=list)


# =============================================================================
# ANALYTICS ENGINE
# =============================================================================

class AnalyticsEngine:
    """
    Advanced Analytics Engine
    
    Features:
    - Multi-metric collection
    - Time-series storage
    - Aggregation functions
    - Trend analysis
    - Anomaly detection
    """

    def __init__(self, retention_days: int = 30):
        self._metrics: Dict[str, Metric] = {}
        self._retention_days = retention_days
        self._aggregations_cache: Dict[str, Any] = {}

    def register_metric(self, name: str, type: MetricType, description: str, unit: str = ""):
        """Register a new metric."""
        self._metrics[name] = Metric(
            name=name,
            type=type,
            description=description,
            unit=unit,
        )
        logger.info(f"Registered metric: {name} ({type.value})")

    def record(self, metric_name: str, value: float, labels: Dict[str, str] = None):
        """Record a metric value."""
        if metric_name not in self._metrics:
            logger.warning(f"Unregistered metric: {metric_name}")
            return
        
        metric = self._metrics[metric_name]
        point = MetricPoint(
            timestamp=datetime.now(),
            value=value,
            labels=labels or {},
        )
        
        metric.points.append(point)
        
        # Cleanup old data
        self._cleanup_old_data(metric)

    def _cleanup_old_data(self, metric: Metric):
        """Remove data older than retention period."""
        cutoff = datetime.now() - timedelta(days=self._retention_days)
        metric.points = [p for p in metric.points if p.timestamp > cutoff]

    def get_metric(self, name: str) -> Optional[Metric]:
        """Get metric by name."""
        return self._metrics.get(name)

    def get_metrics(self) -> List[Metric]:
        """Get all metrics."""
        return list(self._metrics.values())


# =============================================================================
# AGGREGATION FUNCTIONS
# =============================================================================

class AggregationFunctions:
    """Statistical aggregation functions."""

    @staticmethod
    def average(points: List[MetricPoint]) -> float:
        """Calculate average."""
        if not points:
            return 0.0
        return sum(p.value for p in points) / len(points)

    @staticmethod
    def min(points: List[MetricPoint]) -> float:
        """Calculate minimum."""
        if not points:
            return 0.0
        return min(p.value for p in points)

    @staticmethod
    def max(points: List[MetricPoint]) -> float:
        """Calculate maximum."""
        if not points:
            return 0.0
        return max(p.value for p in points)

    @staticmethod
    def sum(points: List[MetricPoint]) -> float:
        """Calculate sum."""
        return sum(p.value for p in points)

    @staticmethod
    def count(points: List[MetricPoint]) -> int:
        """Calculate count."""
        return len(points)

    @staticmethod
    def percentile(points: List[MetricPoint], percentile: float) -> float:
        """Calculate percentile (0-100)."""
        if not points:
            return 0.0
        
        values = sorted(p.value for p in points)
        k = (len(values) - 1) * (percentile / 100)
        f = int(k)
        c = f + 1 if f + 1 < len(values) else f
        
        if f == c:
            return values[f]
        
        return values[f] * (c - k) + values[c] * (k - f)

    @staticmethod
    def std_dev(points: List[MetricPoint]) -> float:
        """Calculate standard deviation."""
        if len(points) < 2:
            return 0.0
        
        avg = AggregationFunctions.average(points)
        variance = sum((p.value - avg) ** 2 for p in points) / len(points)
        return variance ** 0.5


# =============================================================================
# TREND ANALYSIS
# =============================================================================

class TrendAnalysis:
    """Analyze trends in metric data."""

    @staticmethod
    def calculate_trend(points: List[MetricPoint], window_hours: int = 24) -> Dict[str, Any]:
        """
        Calculate trend over time window.
        
        Returns:
            Dict with trend direction, slope, and confidence
        """
        if len(points) < 2:
            return {"direction": "stable", "slope": 0, "confidence": 0}
        
        # Filter to window
        cutoff = datetime.now() - timedelta(hours=window_hours)
        recent_points = [p for p in points if p.timestamp > cutoff]
        
        if len(recent_points) < 2:
            return {"direction": "stable", "slope": 0, "confidence": 0}
        
        # Simple linear regression
        n = len(recent_points)
        sum_x = sum(i for i in range(n))
        sum_y = sum(p.value for p in recent_points)
        sum_xy = sum(i * p.value for i, p in enumerate(recent_points))
        sum_x2 = sum(i ** 2 for i in range(n))
        
        slope = (n * sum_xy - sum_x * sum_y) / (n * sum_x2 - sum_x ** 2) if (n * sum_x2 - sum_x ** 2) != 0 else 0
        
        # Determine direction
        if slope > 0.01:
            direction = "increasing"
        elif slope < -0.01:
            direction = "decreasing"
        else:
            direction = "stable"
        
        # Calculate R-squared (confidence)
        y_pred = [sum_y / n + slope * i for i in range(n)]
        ss_res = sum((p.value - yp) ** 2 for p, yp in zip(recent_points, y_pred))
        ss_tot = sum((p.value - sum_y / n) ** 2 for p in recent_points)
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0
        
        return {
            "direction": direction,
            "slope": slope,
            "confidence": max(0, r_squared),
            "window_hours": window_hours,
        }

    @staticmethod
    def detect_anomalies(points: List[MetricPoint], std_threshold: float = 2.0) -> List[MetricPoint]:
        """
        Detect anomalous data points.
        
        Args:
            points: Data points
            std_threshold: Number of standard deviations for anomaly
        
        Returns:
            List of anomalous points
        """
        if len(points) < 10:
            return []
        
        avg = AggregationFunctions.average(points)
        std = AggregationFunctions.std_dev(points)
        
        if std == 0:
            return []
        
        anomalies = []
        for point in points:
            z_score = abs(point.value - avg) / std
            if z_score > std_threshold:
                anomalies.append(point)
        
        return anomalies


# =============================================================================
# DASHBOARD GENERATOR
# =============================================================================

class DashboardGenerator:
    """Generate analytics dashboards."""

    def __init__(self, engine: AnalyticsEngine):
        self.engine = engine

    def generate_dashboard(self, dashboard_type: str) -> Dict[str, Any]:
        """Generate dashboard configuration."""
        if dashboard_type == "system_overview":
            return self._generate_system_overview()
        elif dashboard_type == "energy_analytics":
            return self._generate_energy_analytics()
        elif dashboard_type == "presence_analytics":
            return self._generate_presence_analytics()
        elif dashboard_type == "automation_performance":
            return self._generate_automation_performance()
        else:
            return {"error": f"Unknown dashboard type: {dashboard_type}"}

    def _generate_system_overview(self) -> Dict[str, Any]:
        """Generate system overview dashboard."""
        return {
            "title": "System Overview",
            "refresh_interval": 30,
            "panels": [
                {
                    "type": "gauge",
                    "title": "CPU Usage",
                    "metric": "system_cpu_percent",
                    "min": 0,
                    "max": 100,
                    "unit": "%",
                },
                {
                    "type": "gauge",
                    "title": "Memory Usage",
                    "metric": "system_memory_percent",
                    "min": 0,
                    "max": 100,
                    "unit": "%",
                },
                {
                    "type": "timeseries",
                    "title": "Request Rate",
                    "metric": "api_requests_total",
                    "aggregation": "rate",
                    "interval": "1m",
                },
                {
                    "type": "stat",
                    "title": "Uptime",
                    "metric": "system_uptime_seconds",
                    "format": "duration",
                },
            ]
        }

    def _generate_energy_analytics(self) -> Dict[str, Any]:
        """Generate energy analytics dashboard."""
        return {
            "title": "Energy Analytics",
            "refresh_interval": 300,
            "panels": [
                {
                    "type": "timeseries",
                    "title": "Power Consumption",
                    "metric": "energy_power_kw",
                    "aggregation": "average",
                    "interval": "1h",
                },
                {
                    "type": "timeseries",
                    "title": "Solar Production",
                    "metric": "energy_solar_kw",
                    "aggregation": "average",
                    "interval": "1h",
                },
                {
                    "type": "stat",
                    "title": "Today's Savings",
                    "metric": "energy_savings_ct",
                    "format": "currency",
                    "currency": "EUR",
                },
                {
                    "type": "pie",
                    "title": "Device Distribution",
                    "metric": "energy_device_percent",
                },
            ]
        }

    def _generate_presence_analytics(self) -> Dict[str, Any]:
        """Generate presence analytics dashboard."""
        return {
            "title": "Presence Analytics",
            "refresh_interval": 60,
            "panels": [
                {
                    "type": "stat",
                    "title": "Current State",
                    "metric": "presence_state",
                    "mapping": {"0": "Away", "1": "Home"},
                },
                {
                    "type": "gauge",
                    "title": "Confidence",
                    "metric": "presence_confidence",
                    "min": 0,
                    "max": 1,
                    "unit": "%",
                },
                {
                    "type": "timeseries",
                    "title": "Presence History",
                    "metric": "presence_state",
                    "aggregation": "last",
                    "interval": "1h",
                },
                {
                    "type": "table",
                    "title": "Sensor Status",
                    "metrics": ["sensor_pir_active", "sensor_radar_active", "sensor_wifi_active"],
                },
            ]
        }

    def _generate_automation_performance(self) -> Dict[str, Any]:
        """Generate automation performance dashboard."""
        return {
            "title": "Automation Performance",
            "refresh_interval": 300,
            "panels": [
                {
                    "type": "stat",
                    "title": "Total Automations",
                    "metric": "automation_count",
                },
                {
                    "type": "stat",
                    "title": "Executions Today",
                    "metric": "automation_executions_total",
                    "aggregation": "sum",
                    "interval": "1d",
                },
                {
                    "type": "timeseries",
                    "title": "Execution Time",
                    "metric": "automation_execution_seconds",
                    "aggregation": "average",
                    "interval": "1h",
                },
                {
                    "type": "table",
                    "title": "Top Automations",
                    "metric": "automation_execution_count",
                    "sort": "desc",
                    "limit": 10,
                },
            ]
        }


# =============================================================================
# EXPORT FUNCTIONS
# =============================================================================

class DataExporter:
    """Export analytics data."""

    @staticmethod
    def to_csv(metrics: List[Metric], filename: str):
        """Export metrics to CSV."""
        import csv
        
        with open(filename, "w", newline="") as f:
            writer = csv.writer(f)
            
            for metric in metrics:
                writer.writerow([f"Metric: {metric.name}", f"Type: {metric.type.value}", f"Unit: {metric.unit}"])
                writer.writerow(["Timestamp", "Value"] + list(metric.points[0].labels.keys() if metric.points else []))
                
                for point in metric.points:
                    writer.writerow([
                        point.timestamp.isoformat(),
                        point.value,
                    ] + list(point.labels.values()))
                
                writer.writerow([])  # Empty line between metrics
        
        logger.info(f"Exported {len(metrics)} metrics to {filename}")

    @staticmethod
    def to_json(metrics: List[Metric], filename: str):
        """Export metrics to JSON."""
        data = {
            "exported_at": datetime.now().isoformat(),
            "metrics": [
                {
                    "name": m.name,
                    "type": m.type.value,
                    "description": m.description,
                    "unit": m.unit,
                    "points": [
                        {
                            "timestamp": p.timestamp.isoformat(),
                            "value": p.value,
                            "labels": p.labels,
                        }
                        for p in m.points
                    ]
                }
                for m in metrics
            ]
        }
        
        with open(filename, "w") as f:
            json.dump(data, f, indent=2)
        
        logger.info(f"Exported {len(metrics)} metrics to {filename}")

    @staticmethod
    def to_prometheus(metrics: List[Metric], filename: str):
        """Export metrics to Prometheus format."""
        lines = []
        
        for metric in metrics:
            # HELP line
            lines.append(f"# HELP {metric.name} {metric.description}")
            # TYPE line
            lines.append(f"# TYPE {metric.name} {metric.type.value}")
            
            # Data points
            for point in metric.points:
                labels = ",".join(f'{k}="{v}"' for k, v in point.labels.items())
                if labels:
                    lines.append(f"{metric.name}{{{labels}}} {point.value} {int(point.timestamp.timestamp() * 1000)}")
                else:
                    lines.append(f"{metric.name} {point.value} {int(point.timestamp.timestamp() * 1000)}")
        
        with open(filename, "w") as f:
            f.write("\n".join(lines))
        
        logger.info(f"Exported {len(metrics)} metrics to Prometheus format")


# =============================================================================
# HOME ASSISTANT INTEGRATION
# =============================================================================

async def async_setup_analytics(hass, config: Dict[str, Any]):
    """Set up analytics in Home Assistant."""
    engine = AnalyticsEngine(retention_days=config.get("retention_days", 30))
    dashboard_gen = DashboardGenerator(engine)
    
    # Register default metrics
    engine.register_metric("system_cpu_percent", MetricType.GAUGE, "CPU usage percent", "%")
    engine.register_metric("system_memory_percent", MetricType.GAUGE, "Memory usage percent", "%")
    engine.register_metric("api_requests_total", MetricType.COUNTER, "Total API requests")
    engine.register_metric("presence_confidence", MetricType.GAUGE, "Presence detection confidence", "")
    
    # Store in hass.data
    hass.data["pilotsuite_analytics_engine"] = engine
    hass.data["pilotsuite_dashboard_generator"] = dashboard_gen
    
    # Set up periodic data collection
    from homeassistant.helpers.event import async_track_time_interval
    
    async def collect_system_metrics():
        """Collect system metrics."""
        # Would collect actual metrics here
        pass
    
    async_track_time_interval(hass, lambda now: collect_system_metrics(), timedelta(minutes=1))
    
    logger.info("Analytics set up successfully")
    
    return engine, dashboard_gen
