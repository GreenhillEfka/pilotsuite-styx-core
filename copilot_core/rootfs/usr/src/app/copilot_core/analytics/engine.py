"""Analytics Engine — Slice 52.

Analytics and metrics aggregation for PilotSuite Core.

Features:
- Event tracking
- Metric aggregation
- Time-series data
- Dashboard queries
- Data export
- Retention policies
"""
from __future__ import annotations

import logging
import threading
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable, Tuple
from enum import Enum
import uuid
from collections import defaultdict

logger = logging.getLogger(__name__)


class MetricType(Enum):
    """Metric types."""
    COUNTER = "counter"
    GAUGE = "gauge"
    HISTOGRAM = "histogram"
    TIMER = "timer"


class AggregationType(Enum):
    """Aggregation types."""
    SUM = "sum"
    AVG = "avg"
    MIN = "min"
    MAX = "max"
    COUNT = "count"
    P50 = "p50"
    P90 = "p90"
    P99 = "p99"


@dataclass
class Event:
    """Tracked event."""
    event_id: str
    event_type: str
    timestamp: str
    properties: Dict[str, Any] = field(default_factory=dict)
    user_id: Optional[str] = None
    session_id: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp,
            "properties": self.properties,
            "user_id": self.user_id,
            "session_id": self.session_id,
        }


@dataclass
class Metric:
    """Metric data point."""
    metric_id: str
    name: str
    metric_type: MetricType
    value: float
    timestamp: str
    tags: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "metric_id": self.metric_id,
            "name": self.name,
            "metric_type": self.metric_type.value,
            "value": self.value,
            "timestamp": self.timestamp,
            "tags": self.tags,
        }


@dataclass
class MetricBucket:
    """Time-bucketed metric aggregation."""
    name: str
    start_time: str
    end_time: str
    count: int = 0
    sum: float = 0.0
    min: Optional[float] = None
    max: Optional[float] = None
    values: List[float] = field(default_factory=list)
    
    def add(self, value: float) -> None:
        """Add value to bucket."""
        self.count += 1
        self.sum += value
        self.values.append(value)
        
        if self.min is None or value < self.min:
            self.min = value
        if self.max is None or value > self.max:
            self.max = value
    
    def avg(self) -> Optional[float]:
        """Calculate average."""
        if self.count == 0:
            return None
        return self.sum / self.count
    
    def percentile(self, p: float) -> Optional[float]:
        """Calculate percentile."""
        if not self.values:
            return None
        
        sorted_values = sorted(self.values)
        index = int(len(sorted_values) * p / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "count": self.count,
            "sum": self.sum,
            "min": self.min,
            "max": self.max,
            "avg": self.avg(),
            "p50": self.percentile(50),
            "p90": self.percentile(90),
            "p99": self.percentile(99),
        }


class AnalyticsEngine:
    """Analytics and metrics engine."""
    
    def __init__(self, retention_days: int = 30):
        self._retention_days = retention_days
        self._events: List[Event] = []
        self._metrics: Dict[str, List[Metric]] = defaultdict(list)
        self._buckets: Dict[str, Dict[str, MetricBucket]] = defaultdict(dict)
        self._counters: Dict[str, float] = {}
        self._gauges: Dict[str, float] = {}
        self._event_handlers: List[Callable[[Event], None]] = []
        self._lock = threading.Lock()
        
        # Statistics
        self._stats = {
            "total_events": 0,
            "total_metrics": 0,
            "events_by_type": {},
            "metrics_by_name": {},
        }
    
    def track_event(self, event_type: str,
                   properties: Optional[Dict[str, Any]] = None,
                   user_id: Optional[str] = None,
                   session_id: Optional[str] = None) -> str:
        """Track an event."""
        event_id = f"evt_{uuid.uuid4().hex[:16]}"
        
        event = Event(
            event_id=event_id,
            event_type=event_type,
            timestamp=datetime.now(timezone.utc).isoformat(),
            properties=properties or {},
            user_id=user_id,
            session_id=session_id,
        )
        
        with self._lock:
            self._events.append(event)
            
            self._stats["total_events"] += 1
            self._stats["events_by_type"][event_type] = \
                self._stats["events_by_type"].get(event_type, 0) + 1
        
        # Notify handlers
        for handler in self._event_handlers:
            try:
                handler(event)
            except Exception as e:
                logger.exception("Event handler failed: %s", e)
        
        logger.debug("Event tracked: %s (%s)", event_type, event_id)
        
        return event_id
    
    def increment(self, name: str, value: float = 1.0,
                 tags: Optional[Dict[str, str]] = None) -> None:
        """Increment a counter metric."""
        self._record_metric(name, MetricType.COUNTER, value, tags)
        
        with self._lock:
            key = self._metric_key(name, tags)
            self._counters[key] = self._counters.get(key, 0) + value
    
    def decrement(self, name: str, value: float = 1.0,
                 tags: Optional[Dict[str, str]] = None) -> None:
        """Decrement a counter metric."""
        self.increment(name, -value, tags)
    
    def gauge(self, name: str, value: float,
             tags: Optional[Dict[str, str]] = None) -> None:
        """Set a gauge metric."""
        self._record_metric(name, MetricType.GAUGE, value, tags)
        
        with self._lock:
            key = self._metric_key(name, tags)
            self._gauges[key] = value
    
    def timing(self, name: str, duration_ms: float,
              tags: Optional[Dict[str, str]] = None) -> None:
        """Record a timing metric."""
        self._record_metric(name, MetricType.TIMER, duration_ms, tags)
    
    def histogram(self, name: str, value: float,
                 tags: Optional[Dict[str, str]] = None) -> None:
        """Record a histogram value."""
        self._record_metric(name, MetricType.HISTOGRAM, value, tags)
    
    def _record_metric(self, name: str, metric_type: MetricType,
                      value: float, tags: Optional[Dict[str, str]]) -> None:
        """Record a metric."""
        metric_id = f"met_{uuid.uuid4().hex[:16]}"
        timestamp = datetime.now(timezone.utc).isoformat()
        
        metric = Metric(
            metric_id=metric_id,
            name=name,
            metric_type=metric_type,
            value=value,
            timestamp=timestamp,
            tags=tags or {},
        )
        
        with self._lock:
            self._metrics[name].append(metric)
            
            self._stats["total_metrics"] += 1
            self._stats["metrics_by_name"][name] = \
                self._stats["metrics_by_name"].get(name, 0) + 1
            
            # Add to time bucket (1-minute buckets)
            bucket_key = self._bucket_key(timestamp)
            bucket = self._get_or_create_bucket(name, bucket_key)
            bucket.add(value)
    
    def _metric_key(self, name: str, tags: Optional[Dict[str, str]]) -> str:
        """Generate metric key from name and tags."""
        if not tags:
            return name
        
        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{name}{{{tag_str}}}"
    
    def _bucket_key(self, timestamp: str) -> str:
        """Generate bucket key from timestamp."""
        dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
        bucket_dt = dt.replace(second=0, microsecond=0)
        return bucket_dt.isoformat()
    
    def _get_or_create_bucket(self, name: str, bucket_key: str) -> MetricBucket:
        """Get or create a metric bucket."""
        if bucket_key not in self._buckets[name]:
            start = bucket_key
            end_dt = datetime.fromisoformat(bucket_key.replace('Z', '+00:00')) + timedelta(minutes=1)
            end = end_dt.isoformat()
            
            self._buckets[name][bucket_key] = MetricBucket(
                name=name,
                start_time=start,
                end_time=end,
            )
        
        return self._buckets[name][bucket_key]
    
    def get_counter(self, name: str, tags: Optional[Dict[str, str]] = None) -> float:
        """Get counter value."""
        key = self._metric_key(name, tags)
        return self._counters.get(key, 0)
    
    def get_gauge(self, name: str, tags: Optional[Dict[str, str]] = None) -> Optional[float]:
        """Get gauge value."""
        key = self._metric_key(name, tags)
        return self._gauges.get(key)
    
    def get_metric_stats(self, name: str,
                        start_time: Optional[str] = None,
                        end_time: Optional[str] = None,
                        tags: Optional[Dict[str, str]] = None) -> Dict[str, Any]:
        """Get metric statistics."""
        with self._lock:
            metrics = self._metrics.get(name, [])
            
            # Filter by time range
            if start_time:
                metrics = [m for m in metrics if m.timestamp >= start_time]
            if end_time:
                metrics = [m for m in metrics if m.timestamp <= end_time]
            
            # Filter by tags
            if tags:
                metrics = [
                    m for m in metrics
                    if all(m.tags.get(k) == v for k, v in tags.items())
                ]
            
            if not metrics:
                return {"count": 0}
            
            values = [m.value for m in metrics]
            
            return {
                "count": len(values),
                "sum": sum(values),
                "min": min(values),
                "max": max(values),
                "avg": sum(values) / len(values),
                "p50": self._percentile(values, 50),
                "p90": self._percentile(values, 90),
                "p99": self._percentile(values, 99),
            }
    
    def _percentile(self, values: List[float], p: float) -> float:
        """Calculate percentile."""
        if not values:
            return 0.0
        
        sorted_values = sorted(values)
        index = int(len(sorted_values) * p / 100)
        return sorted_values[min(index, len(sorted_values) - 1)]
    
    def get_events(self, event_type: Optional[str] = None,
                  start_time: Optional[str] = None,
                  end_time: Optional[str] = None,
                  user_id: Optional[str] = None,
                  limit: int = 100) -> List[Event]:
        """Get events with filters."""
        with self._lock:
            events = self._events
            
            if event_type:
                events = [e for e in events if e.event_type == event_type]
            
            if start_time:
                events = [e for e in events if e.timestamp >= start_time]
            
            if end_time:
                events = [e for e in events if e.timestamp <= end_time]
            
            if user_id:
                events = [e for e in events if e.user_id == user_id]
            
            return events[:limit]
    
    def get_buckets(self, name: str,
                   start_time: Optional[str] = None,
                   end_time: Optional[str] = None) -> List[MetricBucket]:
        """Get metric buckets."""
        with self._lock:
            buckets = list(self._buckets.get(name, {}).values())
            
            if start_time:
                buckets = [b for b in buckets if b.start_time >= start_time]
            
            if end_time:
                buckets = [b for b in buckets if b.end_time <= end_time]
            
            return buckets
    
    def query(self, name: str, aggregation: AggregationType,
             start_time: str, end_time: str,
             tags: Optional[Dict[str, str]] = None,
             bucket_size_minutes: int = 60) -> List[Dict[str, Any]]:
        """Query metrics with aggregation."""
        with self._lock:
            buckets = self.get_buckets(name, start_time, end_time)
            
            results = []
            
            for bucket in buckets:
                # Apply tag filter
                if tags:
                    # Check if any metric in bucket matches tags
                    matching = False
                    for metric in self._metrics.get(name, []):
                        if (metric.timestamp >= bucket.start_time and
                            metric.timestamp < bucket.end_time and
                            all(metric.tags.get(k) == v for k, v in tags.items())):
                            matching = True
                            break
                    
                    if not matching:
                        continue
                
                result = {
                    "time": bucket.start_time,
                    "name": name,
                }
                
                if aggregation == AggregationType.SUM:
                    result["value"] = bucket.sum
                elif aggregation == AggregationType.AVG:
                    result["value"] = bucket.avg()
                elif aggregation == AggregationType.MIN:
                    result["value"] = bucket.min
                elif aggregation == AggregationType.MAX:
                    result["value"] = bucket.max
                elif aggregation == AggregationType.COUNT:
                    result["value"] = bucket.count
                elif aggregation == AggregationType.P50:
                    result["value"] = bucket.percentile(50)
                elif aggregation == AggregationType.P90:
                    result["value"] = bucket.percentile(90)
                elif aggregation == AggregationType.P99:
                    result["value"] = bucket.percentile(99)
                
                results.append(result)
            
            return results
    
    def on_event(self, handler: Callable[[Event], None]) -> None:
        """Register event handler."""
        self._event_handlers.append(handler)
    
    def export_events(self, format: str = "json") -> str:
        """Export events."""
        import json
        
        with self._lock:
            events = [e.to_dict() for e in self._events]
            
            if format == "json":
                return json.dumps(events, indent=2)
            else:
                # CSV format
                lines = ["event_id,event_type,timestamp,user_id,session_id"]
                for e in events:
                    lines.append(f"{e.event_id},{e.event_type},{e.timestamp},{e.user_id or ''},{e.session_id or ''}")
                return "\n".join(lines)
    
    def export_metrics(self, name: Optional[str] = None, format: str = "json") -> str:
        """Export metrics."""
        import json
        
        with self._lock:
            if name:
                metrics = self._metrics.get(name, [])
            else:
                metrics = []
                for metric_list in self._metrics.values():
                    metrics.extend(metric_list)
            
            data = [m.to_dict() for m in metrics]
            
            if format == "json":
                return json.dumps(data, indent=2)
            else:
                # CSV format
                lines = ["metric_id,name,type,value,timestamp,tags"]
                for m in data:
                    tags_str = ";".join(f"{k}={v}" for k, v in m["tags"].items())
                    lines.append(f"{m['metric_id']},{m['name']},{m['metric_type']},{m['value']},{m['timestamp']},{tags_str}")
                return "\n".join(lines)
    
    def clear_events(self, older_than_days: Optional[int] = None) -> int:
        """Clear events."""
        with self._lock:
            if older_than_days:
                cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
                cutoff_str = cutoff.isoformat()
                
                original_count = len(self._events)
                self._events = [e for e in self._events if e.timestamp >= cutoff_str]
                
                return original_count - len(self._events)
            else:
                count = len(self._events)
                self._events.clear()
                return count
    
    def clear_metrics(self, older_than_days: Optional[int] = None) -> int:
        """Clear metrics."""
        with self._lock:
            if older_than_days:
                cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
                cutoff_str = cutoff.isoformat()
                
                cleared = 0
                for name in list(self._metrics.keys()):
                    original_count = len(self._metrics[name])
                    self._metrics[name] = [
                        m for m in self._metrics[name]
                        if m.timestamp >= cutoff_str
                    ]
                    cleared += original_count - len(self._metrics[name])
                
                return cleared
            else:
                count = sum(len(m) for m in self._metrics.values())
                self._metrics.clear()
                self._buckets.clear()
                return count
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get analytics statistics."""
        with self._lock:
            return {
                **self._stats,
                "total_events_stored": len(self._events),
                "total_metrics_stored": sum(len(m) for m in self._metrics.values()),
                "total_buckets": sum(len(b) for b in self._buckets.values()),
                "total_counters": len(self._counters),
                "total_gauges": len(self._gauges),
                "retention_days": self._retention_days,
            }
    
    def apply_retention(self) -> Tuple[int, int]:
        """Apply retention policy."""
        events_cleared = self.clear_events(older_than_days=self._retention_days)
        metrics_cleared = self.clear_metrics(older_than_days=self._retention_days)
        
        return events_cleared, metrics_cleared


def create_analytics_engine(retention_days: int = 30) -> AnalyticsEngine:
    """Factory function to create analytics engine."""
    return AnalyticsEngine(retention_days=retention_days)
