"""Metrics Engine — Slice 37.

System metrics collection and aggregation for PilotSuite Core.

Features:
- Counter, gauge, histogram metrics
- Time-series data storage
- Aggregation functions (avg, min, max, sum, percentiles)
- Metric labeling and filtering
- Export formats (Prometheus, JSON)
- Alerting thresholds
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import uuid
import math

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Metric type."""
    COUNTER = "counter"  # Monotonically increasing
    GAUGE = "gauge"  # Can go up or down
    HISTOGRAM = "histogram"  # Distribution of values
    SUMMARY = "summary"  # Pre-calculated percentiles


@dataclass
class MetricPoint:
    """Single metric data point."""
    timestamp: str
    value: float
    labels: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "value": self.value,
            "labels": self.labels,
        }


@dataclass
class Metric:
    """Metric definition."""
    name: str
    description: str
    metric_type: MetricType
    unit: str = ""
    labels: List[str] = field(default_factory=list)
    points: List[MetricPoint] = field(default_factory=list)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    # For counters
    initial_value: float = 0.0
    
    # For histograms
    buckets: List[float] = field(default_factory=lambda: [0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0])
    bucket_counts: Dict[float, int] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "metric_type": self.metric_type.value,
            "unit": self.unit,
            "labels": self.labels,
            "point_count": len(self.points),
            "created_at": self.created_at,
        }


@dataclass
class AlertThreshold:
    """Alert threshold definition."""
    threshold_id: str
    metric_name: str
    condition: str  # gt, gte, lt, lte, eq
    value: float
    duration_seconds: int = 0  # Must breach for this duration
    severity: str = "warning"
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "threshold_id": self.threshold_id,
            "metric_name": self.metric_name,
            "condition": self.condition,
            "value": self.value,
            "duration_seconds": self.duration_seconds,
            "severity": self.severity,
            "enabled": self.enabled,
        }


class MetricsEngine:
    """System metrics collection engine."""
    
    _TIME_RANGE_EDGE_GRACE = timedelta(seconds=1)
    
    def __init__(self, retention_hours: int = 24, max_points_per_metric: int = 10000):
        self._metrics: Dict[str, Metric] = {}
        self._thresholds: Dict[str, AlertThreshold] = {}
        self._alerts: List[Dict[str, Any]] = []
        self._retention = timedelta(hours=retention_hours)
        self._max_points = max_points_per_metric
        
        # Callbacks for alert notifications
        self._alert_callbacks: List[Callable] = []

    @staticmethod
    def _parse_iso_timestamp(value: str) -> datetime:
        """Parse ISO timestamps with stable UTC handling."""
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    
    def register_metric(self, name: str, description: str,
                       metric_type: str, unit: str = "",
                       labels: Optional[List[str]] = None,
                       buckets: Optional[List[float]] = None) -> None:
        """Register a new metric."""
        mtype = MetricType(metric_type)
        
        metric = Metric(
            name=name,
            description=description,
            metric_type=mtype,
            unit=unit,
            labels=labels or [],
        )
        
        if buckets and mtype == MetricType.HISTOGRAM:
            metric.buckets = sorted(buckets)
            metric.bucket_counts = {b: 0 for b in metric.buckets}
        
        self._metrics[name] = metric
        
        logger.info("Metric registered: %s (%s)", name, metric_type)
    
    def increment(self, name: str, value: float = 1.0,
                 labels: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric."""
        if name not in self._metrics:
            self.register_metric(name, f"Counter: {name}", "counter")
        
        metric = self._metrics[name]
        
        if metric.metric_type != MetricType.COUNTER:
            logger.warning("Metric %s is not a counter", name)
            return
        
        now = datetime.now(timezone.utc)
        
        # Get or create point for this label combination
        point = self._get_or_create_point(metric, labels, now)
        point.value += value
        
        self._add_point(metric, point)
    
    def set_gauge(self, name: str, value: float,
                 labels: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric value."""
        if name not in self._metrics:
            self.register_metric(name, f"Gauge: {name}", "gauge")
        
        metric = self._metrics[name]
        
        if metric.metric_type != MetricType.GAUGE:
            logger.warning("Metric %s is not a gauge", name)
            return
        
        now = datetime.now(timezone.utc)
        point = MetricPoint(timestamp=now.isoformat(), value=value, labels=labels or {})
        
        self._add_point(metric, point)
        
        # Check thresholds
        self._check_thresholds(name, value, now)
    
    def observe_histogram(self, name: str, value: float,
                         labels: Optional[Dict[str, str]] = None) -> None:
        """Observe a value for histogram metric."""
        if name not in self._metrics:
            self.register_metric(name, f"Histogram: {name}", "histogram",
                               buckets=[0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0])
        
        metric = self._metrics[name]
        
        if metric.metric_type != MetricType.HISTOGRAM:
            logger.warning("Metric %s is not a histogram", name)
            return
        
        now = datetime.now(timezone.utc)
        
        # Update bucket counts
        for bucket in metric.buckets:
            if value <= bucket:
                metric.bucket_counts[bucket] = metric.bucket_counts.get(bucket, 0) + 1
        
        # Also store as point for time-series
        point = MetricPoint(timestamp=now.isoformat(), value=value, labels=labels or {})
        self._add_point(metric, point)
    
    def _get_or_create_point(self, metric: Metric,
                            labels: Optional[Dict[str, str]],
                            timestamp: datetime) -> MetricPoint:
        """Create a fresh point seeded from the latest value for this label set."""
        labels = labels or {}
        
        # Seed a new time-series point from the latest matching cumulative value
        # instead of mutating a historical point in place.
        for point in reversed(metric.points):
            if point.labels == labels:
                return MetricPoint(
                    timestamp=timestamp.isoformat(),
                    value=point.value,
                    labels=dict(labels),
                )
        
        return MetricPoint(timestamp=timestamp.isoformat(), value=metric.initial_value, labels=dict(labels))
    
    def _add_point(self, metric: Metric, point: MetricPoint) -> None:
        """Add point to metric, respecting max points limit."""
        metric.points.append(point)
        
        # Trim if needed
        if len(metric.points) > self._max_points:
            metric.points = metric.points[-self._max_points:]
    
    def _check_thresholds(self, metric_name: str, value: float,
                         timestamp: datetime) -> None:
        """Check alert thresholds."""
        for threshold in self._thresholds.values():
            if threshold.metric_name != metric_name:
                continue
            
            if not threshold.enabled:
                continue
            
            breached = False
            
            if threshold.condition == "gt" and value > threshold.value:
                breached = True
            elif threshold.condition == "gte" and value >= threshold.value:
                breached = True
            elif threshold.condition == "lt" and value < threshold.value:
                breached = True
            elif threshold.condition == "lte" and value <= threshold.value:
                breached = True
            elif threshold.condition == "eq" and value == threshold.value:
                breached = True
            
            if breached:
                alert = {
                    "alert_id": f"alert_{uuid.uuid4().hex[:8]}",
                    "threshold_id": threshold.threshold_id,
                    "metric_name": metric_name,
                    "value": value,
                    "threshold_value": threshold.value,
                    "condition": threshold.condition,
                    "severity": threshold.severity,
                    "timestamp": timestamp.isoformat(),
                }
                
                self._alerts.append(alert)
                
                # Notify callbacks
                for callback in self._alert_callbacks:
                    try:
                        callback(alert)
                    except Exception as exc:
                        logger.exception("Alert callback failed: %s", exc)
    
    def register_threshold(self, metric_name: str, condition: str,
                          value: float, severity: str = "warning",
                          duration_seconds: int = 0) -> str:
        """Register alert threshold."""
        threshold_id = f"thresh_{uuid.uuid4().hex[:8]}"
        
        threshold = AlertThreshold(
            threshold_id=threshold_id,
            metric_name=metric_name,
            condition=condition,
            value=value,
            duration_seconds=duration_seconds,
            severity=severity,
        )
        
        self._thresholds[threshold_id] = threshold
        
        logger.info("Threshold registered: %s for %s %s %f", threshold_id, metric_name, condition, value)
        
        return threshold_id
    
    def enable_threshold(self, threshold_id: str) -> bool:
        """Enable a threshold."""
        if threshold_id not in self._thresholds:
            return False
        
        self._thresholds[threshold_id].enabled = True
        return True
    
    def disable_threshold(self, threshold_id: str) -> bool:
        """Disable a threshold."""
        if threshold_id not in self._thresholds:
            return False
        
        self._thresholds[threshold_id].enabled = False
        return True
    
    def register_alert_callback(self, callback: Callable) -> None:
        """Register callback for alert notifications."""
        self._alert_callbacks.append(callback)
    
    def get_metric(self, name: str) -> Optional[Dict[str, Any]]:
        """Get metric definition."""
        if name not in self._metrics:
            return None
        
        return self._metrics[name].to_dict()
    
    def get_metric_value(self, name: str,
                        labels: Optional[Dict[str, str]] = None,
                        aggregation: str = "last") -> Optional[float]:
        """Get current metric value with optional aggregation."""
        if name not in self._metrics:
            return None
        
        metric = self._metrics[name]
        
        if not metric.points:
            return None
        
        # Filter by labels
        points = metric.points
        if labels:
            points = [p for p in points if p.labels == labels]
        
        if not points:
            return None
        
        if aggregation == "last":
            return points[-1].value
        elif aggregation == "first":
            return points[0].value
        elif aggregation == "avg":
            return sum(p.value for p in points) / len(points)
        elif aggregation == "min":
            return min(p.value for p in points)
        elif aggregation == "max":
            return max(p.value for p in points)
        elif aggregation == "sum":
            if metric.metric_type == MetricType.COUNTER:
                latest_by_series: Dict[tuple[tuple[str, str], ...], float] = {}
                for point in points:
                    series_key = tuple(sorted(point.labels.items()))
                    latest_by_series[series_key] = point.value
                return sum(latest_by_series.values())
            return sum(p.value for p in points)
        
        return points[-1].value
    
    def get_metric_history(self, name: str,
                          start_time: Optional[str] = None,
                          end_time: Optional[str] = None,
                          labels: Optional[Dict[str, str]] = None,
                          limit: int = 100) -> List[Dict[str, Any]]:
        """Get metric history."""
        if name not in self._metrics:
            return []
        
        metric = self._metrics[name]
        points = metric.points
        
        # Filter by labels
        if labels:
            points = [p for p in points if p.labels == labels]
        
        # Filter by time range
        if start_time:
            start = self._parse_iso_timestamp(start_time)
            points = [p for p in points if self._parse_iso_timestamp(p.timestamp) >= start]
        
        if end_time:
            end = self._parse_iso_timestamp(end_time)
            now = datetime.now(timezone.utc)
            if now >= end and (now - end) <= self._TIME_RANGE_EDGE_GRACE:
                end = now
            points = [p for p in points if self._parse_iso_timestamp(p.timestamp) <= end]
        
        # Sort by timestamp and limit
        points.sort(key=lambda p: p.timestamp, reverse=True)
        
        return [p.to_dict() for p in points[:limit]]
    
    def get_all_metrics(self) -> List[Dict[str, Any]]:
        """Get all registered metrics."""
        return [m.to_dict() for m in self._metrics.values()]
    
    def get_alerts(self, metric_name: Optional[str] = None,
                  severity: Optional[str] = None,
                  limit: int = 100) -> List[Dict[str, Any]]:
        """Get triggered alerts."""
        alerts = self._alerts
        
        if metric_name:
            alerts = [a for a in alerts if a["metric_name"] == metric_name]
        
        if severity:
            alerts = [a for a in alerts if a["severity"] == severity]
        
        # Sort by timestamp (newest first)
        alerts.sort(key=lambda a: a["timestamp"], reverse=True)
        
        return alerts[:limit]
    
    def get_thresholds(self) -> List[Dict[str, Any]]:
        """Get all thresholds."""
        return [t.to_dict() for t in self._thresholds.values()]
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get metrics statistics."""
        total_points = sum(len(m.points) for m in self._metrics.values())
        
        by_type = {}
        for metric in self._metrics.values():
            mtype = metric.metric_type.value
            by_type[mtype] = by_type.get(mtype, 0) + 1
        
        return {
            "total_metrics": len(self._metrics),
            "total_points": total_points,
            "by_type": by_type,
            "total_thresholds": len(self._thresholds),
            "total_alerts": len(self._alerts),
        }
    
    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        for metric in self._metrics.values():
            # HELP line
            lines.append(f"# HELP {metric.name} {metric.description}")
            
            # TYPE line
            lines.append(f"# TYPE {metric.name} {metric.metric_type.value}")
            
            # Value lines
            if metric.points:
                series_points: Dict[tuple[tuple[str, str], ...], List[MetricPoint]] = {}
                for point in metric.points:
                    series_key = tuple(sorted(point.labels.items()))
                    series_points.setdefault(series_key, []).append(point)
                
                for series_key, series in series_points.items():
                    latest = series[-1]
                    labels_parts = [f'{k}="{v}"' for k, v in series_key]
                    labels_str = f"{{{','.join(labels_parts)}}}" if labels_parts else ""
                    
                    if metric.metric_type == MetricType.HISTOGRAM:
                        for bucket in sorted(metric.buckets):
                            count = sum(1 for point in series if point.value <= bucket)
                            bucket_labels = [f'le="{bucket}"', *labels_parts]
                            lines.append(f"{metric.name}_bucket{{{','.join(bucket_labels)}}} {count}")
                        lines.append(f"{metric.name}_count{labels_str} {len(series)}")
                        lines.append(f"{metric.name}_sum{labels_str} {sum(point.value for point in series)}")
                    else:
                        lines.append(f"{metric.name}{labels_str} {latest.value}")
            
            lines.append("")
        
        return "\n".join(lines)
    
    def export_json(self) -> str:
        """Export metrics as JSON."""
        import json
        
        data = {
            "metrics": {},
            "alerts": self._alerts[-100:],  # Last 100 alerts
        }
        
        for metric in self._metrics.values():
            data["metrics"][metric.name] = {
                "definition": metric.to_dict(),
                "latest_value": self.get_metric_value(metric.name),
                "history": self.get_metric_history(metric.name, limit=10),
            }
        
        return json.dumps(data, indent=2)
    
    def cleanup_old_data(self, older_than: Optional[str] = None) -> int:
        """Clean up old metric data."""
        if older_than:
            cutoff = datetime.fromisoformat(older_than)
        else:
            cutoff = datetime.now(timezone.utc) - self._retention
        
        removed = 0
        
        for metric in self._metrics.values():
            initial_count = len(metric.points)
            metric.points = [
                p for p in metric.points
                if datetime.fromisoformat(p.timestamp) >= cutoff
            ]
            removed += initial_count - len(metric.points)
        
        return removed
    
    def reset_metric(self, name: str) -> bool:
        """Reset a metric (clear all points)."""
        if name not in self._metrics:
            return False
        
        self._metrics[name].points.clear()
        if self._metrics[name].metric_type == MetricType.HISTOGRAM:
            self._metrics[name].bucket_counts = {b: 0 for b in self._metrics[name].buckets}
        
        return True
    
    def delete_metric(self, name: str) -> bool:
        """Delete a metric."""
        if name not in self._metrics:
            return False
        
        del self._metrics[name]
        return True


def create_metrics_engine(retention_hours: int = 24) -> MetricsEngine:
    """Factory function to create metrics engine."""
    return MetricsEngine(retention_hours=retention_hours)
