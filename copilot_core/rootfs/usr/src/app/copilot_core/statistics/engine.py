"""Statistics & Analytics Engine — Slice 21.

Unified statistics and analytics for PilotSuite Core.

Features:
- Cross-module statistics aggregation
- Trend analysis and forecasting
- Usage pattern recognition
- Energy/water/consumption analytics
- Custom metric definitions
- Historical data queries
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import math

logger = logging.getLogger(__name__)


class AggregationType(Enum):
    """Type of aggregation."""
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    SUM = "sum"
    COUNT = "count"
    MEDIAN = "median"
    STDDEV = "stddev"


class TrendDirection(Enum):
    """Trend direction."""
    INCREASING = "increasing"
    DECREASING = "decreasing"
    STABLE = "stable"
    VOLATILE = "volatile"


@dataclass
class DataPoint:
    """Single data point."""
    timestamp: str
    value: float
    entity_id: Optional[str] = None
    zone_id: Optional[str] = None
    module_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "value": self.value,
            "entity_id": self.entity_id,
            "zone_id": self.zone_id,
            "module_id": self.module_id,
            "metadata": self.metadata,
        }


@dataclass
class MetricDefinition:
    """Custom metric definition."""
    metric_id: str
    name: str
    description: str
    unit: str
    aggregation: AggregationType
    source_entities: List[str]
    calculation: Optional[str] = None  # Custom calculation expression
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "name": self.name,
            "description": self.description,
            "unit": self.unit,
            "aggregation": self.aggregation.value,
            "source_entities": self.source_entities,
            "calculation": self.calculation,
            "enabled": self.enabled,
        }


@dataclass
class TrendAnalysis:
    """Trend analysis result."""
    metric_id: str
    direction: TrendDirection
    slope: float  # Rate of change per hour
    confidence: float  # 0.0-1.0
    r_squared: float  # Goodness of fit
    forecast_1h: Optional[float] = None
    forecast_24h: Optional[float] = None
    anomalies_detected: int = 0
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "direction": self.direction.value,
            "slope": self.slope,
            "confidence": self.confidence,
            "r_squared": self.r_squared,
            "forecast_1h": self.forecast_1h,
            "forecast_24h": self.forecast_24h,
            "anomalies_detected": self.anomalies_detected,
        }


class StatisticsEngine:
    """Statistics and analytics engine."""
    
    def __init__(self):
        self._data_points: Dict[str, List[DataPoint]] = {}  # metric_id -> points
        self._metrics: Dict[str, MetricDefinition] = {}
        self._max_points_per_metric = 10000
        
        # Pre-computed statistics cache
        self._stats_cache: Dict[str, Dict[str, Any]] = {}
        self._cache_ttl_seconds = 300  # 5 minutes
    
    def define_metric(self, metric_id: str, name: str, description: str,
                     unit: str, aggregation: AggregationType,
                     source_entities: List[str],
                     calculation: Optional[str] = None) -> str:
        """Define a custom metric."""
        metric = MetricDefinition(
            metric_id=metric_id,
            name=name,
            description=description,
            unit=unit,
            aggregation=aggregation,
            source_entities=source_entities,
            calculation=calculation,
        )
        
        self._metrics[metric_id] = metric
        
        if metric_id not in self._data_points:
            self._data_points[metric_id] = []
        
        return metric_id
    
    def add_data_point(self, metric_id: str, value: float,
                      entity_id: Optional[str] = None,
                      zone_id: Optional[str] = None,
                      module_id: Optional[str] = None,
                      metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add data point for a metric."""
        if metric_id not in self._data_points:
            self._data_points[metric_id] = []
        
        point = DataPoint(
            timestamp=datetime.now(timezone.utc).isoformat(),
            value=value,
            entity_id=entity_id,
            zone_id=zone_id,
            module_id=module_id,
            metadata=metadata or {},
        )
        
        self._data_points[metric_id].append(point)
        
        # Trim if too many points
        if len(self._data_points[metric_id]) > self._max_points_per_metric:
            self._data_points[metric_id] = self._data_points[metric_id][-self._max_points_per_metric:]
        
        # Invalidate cache
        self._stats_cache.pop(metric_id, None)
    
    def get_statistics(self, metric_id: str, hours: int = 24) -> Dict[str, Any]:
        """Get statistics for a metric."""
        # Check cache
        if metric_id in self._stats_cache:
            cached = self._stats_cache[metric_id]
            if (datetime.now(timezone.utc) - datetime.fromisoformat(cached["computed_at"])).total_seconds() < self._cache_ttl_seconds:
                return cached["stats"]
        
        points = self._get_points(metric_id, hours)
        
        if not points:
            return {
                "count": 0,
                "avg": None,
                "min": None,
                "max": None,
                "sum": None,
                "median": None,
                "stddev": None,
                "first": None,
                "last": None,
            }
        
        values = [p.value for p in points]
        
        stats = {
            "count": len(values),
            "avg": sum(values) / len(values),
            "min": min(values),
            "max": max(values),
            "sum": sum(values),
            "median": self._calculate_median(values),
            "stddev": self._calculate_stddev(values),
            "first": points[0].value if points else None,
            "last": points[-1].value if points else None,
            "computed_at": datetime.now(timezone.utc).isoformat(),
        }
        
        # Cache results
        self._stats_cache[metric_id] = {
            "stats": stats,
            "computed_at": stats["computed_at"],
        }
        
        return stats
    
    def get_trend(self, metric_id: str, hours: int = 24) -> TrendAnalysis:
        """Analyze trend for a metric."""
        points = self._get_points(metric_id, hours)
        
        if len(points) < 3:
            return TrendAnalysis(
                metric_id=metric_id,
                direction=TrendDirection.STABLE,
                slope=0.0,
                confidence=0.0,
                r_squared=0.0,
            )
        
        # Linear regression
        x_vals = list(range(len(points)))
        y_vals = [p.value for p in points]
        
        slope, intercept, r_squared = self._linear_regression(x_vals, y_vals)
        
        # Determine direction
        if abs(slope) < 0.01:
            direction = TrendDirection.STABLE
        elif slope > 0:
            direction = TrendDirection.INCREASING
        else:
            direction = TrendDirection.DECREASING
        
        # Calculate confidence based on r_squared and point count
        confidence = min(1.0, r_squared * (len(points) / 10))
        
        # Forecast
        next_x = len(points)
        forecast_1h = slope * (next_x + 1) + intercept if hours >= 1 else None
        forecast_24h = slope * (next_x + 24) + intercept if hours >= 24 else None
        
        # Detect anomalies
        anomalies = self._detect_anomalies(points)
        
        return TrendAnalysis(
            metric_id=metric_id,
            direction=direction,
            slope=slope,
            confidence=confidence,
            r_squared=r_squared,
            forecast_1h=forecast_1h,
            forecast_24h=forecast_24h,
            anomalies_detected=len(anomalies),
        )
    
    def get_hourly_breakdown(self, metric_id: str, hours: int = 24) -> List[Dict[str, Any]]:
        """Get hourly breakdown of metric values."""
        points = self._get_points(metric_id, hours)
        
        if not points:
            return []
        
        # Group by hour
        hourly: Dict[str, List[float]] = {}
        
        for point in points:
            dt = datetime.fromisoformat(point.timestamp)
            hour_key = dt.strftime("%Y-%m-%d %H:00")
            
            if hour_key not in hourly:
                hourly[hour_key] = []
            hourly[hour_key].append(point.value)
        
        # Calculate hourly stats
        result = []
        for hour_key in sorted(hourly.keys()):
            values = hourly[hour_key]
            result.append({
                "hour": hour_key,
                "avg": sum(values) / len(values),
                "min": min(values),
                "max": max(values),
                "count": len(values),
            })
        
        return result
    
    def compare_periods(self, metric_id: str, hours_current: int = 24,
                       hours_previous: int = 24) -> Dict[str, Any]:
        """Compare two time periods."""
        now = datetime.now(timezone.utc)
        
        # Get current period points
        current_points = self._get_points(metric_id, hours_current)
        current_values = [p.value for p in current_points]
        
        # Get previous period points (shifted back)
        previous_cutoff = now - timedelta(hours=hours_current)
        previous_start = previous_cutoff - timedelta(hours=hours_previous)
        
        previous_points = [
            p for p in self._data_points.get(metric_id, [])
            if previous_start <= datetime.fromisoformat(p.timestamp) <= previous_cutoff
        ]
        previous_values = [p.value for p in previous_points]
        
        if not current_values or not previous_values:
            return {
                "current_avg": sum(current_values) / len(current_values) if current_values else None,
                "previous_avg": sum(previous_values) / len(previous_values) if previous_values else None,
                "change_absolute": None,
                "change_percent": None,
            }
        
        current_avg = sum(current_values) / len(current_values)
        previous_avg = sum(previous_values) / len(previous_values)
        
        change_absolute = current_avg - previous_avg
        change_percent = (change_absolute / previous_avg * 100) if previous_avg != 0 else 0
        
        return {
            "current_avg": current_avg,
            "previous_avg": previous_avg,
            "change_absolute": change_absolute,
            "change_percent": change_percent,
            "trend": "up" if change_absolute > 0 else "down" if change_absolute < 0 else "stable",
        }
    
    def get_all_metrics(self) -> List[Dict[str, Any]]:
        """Get all defined metrics."""
        return [m.to_dict() for m in self._metrics.values()]
    
    def _get_points(self, metric_id: str, hours: int) -> List[DataPoint]:
        """Get data points for a metric within time window."""
        if metric_id not in self._data_points:
            return []
        
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        
        return [
            p for p in self._data_points[metric_id]
            if datetime.fromisoformat(p.timestamp) >= cutoff
        ]
    
    def _calculate_median(self, values: List[float]) -> float:
        """Calculate median."""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        n = len(sorted_values)
        mid = n // 2
        
        if n % 2 == 0:
            return (sorted_values[mid - 1] + sorted_values[mid]) / 2
        else:
            return sorted_values[mid]
    
    def _calculate_stddev(self, values: List[float]) -> float:
        """Calculate standard deviation."""
        if len(values) < 2:
            return 0.0
        
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return math.sqrt(variance)
    
    def _linear_regression(self, x: List[float], y: List[float]) -> tuple:
        """Calculate linear regression (slope, intercept, r_squared)."""
        n = len(x)
        if n < 2:
            return 0.0, 0.0, 0.0
        
        sum_x = sum(x)
        sum_y = sum(y)
        sum_xy = sum(xi * yi for xi, yi in zip(x, y))
        sum_x2 = sum(xi ** 2 for xi in x)
        sum_y2 = sum(yi ** 2 for yi in y)
        
        denominator = n * sum_x2 - sum_x ** 2
        if denominator == 0:
            return 0.0, sum_y / n, 0.0
        
        slope = (n * sum_xy - sum_x * sum_y) / denominator
        intercept = (sum_y - slope * sum_x) / n
        
        # R-squared
        y_mean = sum_y / n
        ss_tot = sum((yi - y_mean) ** 2 for yi in y)
        ss_res = sum((yi - (slope * xi + intercept)) ** 2 for xi, yi in zip(x, y))
        
        r_squared = 1 - (ss_res / ss_tot) if ss_tot != 0 else 0.0
        
        return slope, intercept, r_squared
    
    def _detect_anomalies(self, points: List[DataPoint], threshold_stddev: float = 2.0) -> List[DataPoint]:
        """Detect anomalies using z-score."""
        if len(points) < 3:
            return []
        
        values = [p.value for p in points]
        mean = sum(values) / len(values)
        stddev = self._calculate_stddev(values)
        
        if stddev == 0:
            return []
        
        anomalies = []
        for point in points:
            z_score = abs((point.value - mean) / stddev)
            if z_score > threshold_stddev:
                anomalies.append(point)
        
        return anomalies


def create_statistics_engine() -> StatisticsEngine:
    """Factory function to create statistics engine."""
    return StatisticsEngine()
