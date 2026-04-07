"""P1-002: Observability — Structured Logging, Metrics, Tracing."""
from __future__ import annotations

import json
import logging
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Any, Optional
from enum import Enum


class LogLevel(Enum):
    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


@dataclass
class LogEntry:
    """Structured log entry."""
    timestamp: float
    level: str
    message: str
    logger: str
    module: Optional[str] = None
    operation: Optional[str] = None
    duration_ms: Optional[float] = None
    metadata: dict = field(default_factory=dict)

    def to_json(self) -> str:
        return json.dumps({
            "timestamp": self.timestamp,
            "level": self.level,
            "message": self.message,
            "logger": self.logger,
            "module": self.module,
            "operation": self.operation,
            "duration_ms": self.duration_ms,
            **self.metadata
        })


@dataclass
class MetricPoint:
    """Single metric data point."""
    name: str
    value: float
    timestamp: float = field(default_factory=time.time)
    tags: dict = field(default_factory=dict)
    metric_type: str = "gauge"  # gauge, counter, histogram


class MetricsCollector:
    """Collects and aggregates metrics."""

    def __init__(self):
        self._metrics: list[MetricPoint] = []
        self._counters: dict[str, float] = {}
        self._gauges: dict[str, float] = {}
        self._histograms: dict[str, list[float]] = {}

    def increment_counter(self, name: str, value: float = 1.0, tags: Optional[dict] = None):
        """Increment a counter metric."""
        key = f"{name}:{json.dumps(tags, sort_keys=True)}" if tags else name
        self._counters[key] = self._counters.get(key, 0) + value
        self._metrics.append(MetricPoint(name=name, value=value, tags=tags or {}, metric_type="counter"))

    def set_gauge(self, name: str, value: float, tags: Optional[dict] = None):
        """Set a gauge metric."""
        key = f"{name}:{json.dumps(tags, sort_keys=True)}" if tags else name
        self._gauges[key] = value
        self._metrics.append(MetricPoint(name=name, value=value, tags=tags or {}, metric_type="gauge"))

    def record_histogram(self, name: str, value: float, tags: Optional[dict] = None):
        """Record a histogram value."""
        key = f"{name}:{json.dumps(tags, sort_keys=True)}" if tags else name
        if key not in self._histograms:
            self._histograms[key] = []
        self._histograms[key].append(value)
        self._metrics.append(MetricPoint(name=name, value=value, tags=tags or {}, metric_type="histogram"))

    def get_metrics(self, name_filter: Optional[str] = None) -> list[MetricPoint]:
        """Get collected metrics."""
        if name_filter:
            return [m for m in self._metrics if m.name.startswith(name_filter)]
        return self._metrics[-1000:]  # Last 1000 points

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        for key, value in self._counters.items():
            name = key.split(':')[0]
            lines.append(f"# TYPE {name} counter")
            lines.append(f"{key} {value}")
        for key, value in self._gauges.items():
            name = key.split(':')[0]
            lines.append(f"# TYPE {name} gauge")
            lines.append(f"{key} {value}")
        return "\n".join(lines)


class TracingContext:
    """Distributed tracing context."""

    def __init__(self, trace_id: str, span_id: str, parent_span_id: Optional[str] = None):
        self.trace_id = trace_id
        self.span_id = span_id
        self.parent_span_id = parent_span_id
        self.operation_name: str = ""
        self.start_time: Optional[float] = None
        self.end_time: Optional[float] = None
        self.tags: dict = {}
        self.logs: list[dict] = []

    def start(self):
        self.start_time = time.time()

    def end(self):
        self.end_time = time.time()

    @property
    def duration_ms(self) -> Optional[float]:
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time) * 1000
        return None

    def to_dict(self) -> dict:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "parent_span_id": self.parent_span_id,
            "operation_name": self.operation_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "tags": self.tags,
            "logs": self.logs
        }


class ObservabilityEngine:
    """Central observability engine."""

    def __init__(self, service_name: str = "pilotsuite-core"):
        self.service_name = service_name
        self.logger = logging.getLogger(service_name)
        self.metrics = MetricsCollector()
        self._active_traces: dict[str, TracingContext] = {}

    def log(self, level: LogLevel, message: str, **kwargs):
        """Log structured message."""
        entry = LogEntry(
            timestamp=time.time(),
            level=level.value,
            message=message,
            logger=self.service_name,
            metadata=kwargs
        )
        log_method = getattr(self.logger, level.value.lower(), self.logger.info)
        log_method(f"{entry.to_json()}")

    @contextmanager
    def trace(self, operation: str, trace_id: Optional[str] = None):
        """Context manager for tracing."""
        import uuid
        trace_id = trace_id or str(uuid.uuid4())
        span_id = str(uuid.uuid4())

        ctx = TracingContext(trace_id=trace_id, span_id=span_id)
        ctx.operation_name = operation
        ctx.start()
        self._active_traces[span_id] = ctx

        try:
            yield ctx
            ctx.end()
            self.log(LogLevel.DEBUG, f"Trace complete: {operation}", duration_ms=ctx.duration_ms)
        except Exception as e:
            ctx.tags["error"] = str(e)
            ctx.end()
            self.log(LogLevel.ERROR, f"Trace failed: {operation}", duration_ms=ctx.duration_ms, error=str(e))
            raise
        finally:
            del self._active_traces[span_id]

    def record_metric(self, name: str, value: float, tags: Optional[dict] = None, metric_type: str = "gauge"):
        """Record a metric."""
        if metric_type == "counter":
            self.metrics.increment_counter(name, value, tags)
        elif metric_type == "histogram":
            self.metrics.record_histogram(name, value, tags)
        else:
            self.metrics.set_gauge(name, value, tags)


# Global default observability engine
default_observability = ObservabilityEngine()


def trace_operation(operation: str):
    """Decorator for tracing operations."""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            with default_observability.trace(operation) as ctx:
                ctx.tags["function"] = func.__name__
                return await func(*args, **kwargs)
        return wrapper
    return decorator
