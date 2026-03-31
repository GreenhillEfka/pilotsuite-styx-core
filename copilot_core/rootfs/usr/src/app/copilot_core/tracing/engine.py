"""Tracing Engine — Slice 48.

Distributed tracing for PilotSuite Core.

Features:
- Trace and span creation
- Context propagation
- Span attributes and events
- Trace sampling
- Span relationships (parent/child)
- Trace export
- Performance metrics
"""
from __future__ import annotations

import logging
import threading
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class SpanStatus(Enum):
    """Span status."""
    UNSET = "unset"
    OK = "ok"
    ERROR = "error"


class SpanKind(Enum):
    """Span kind."""
    INTERNAL = "internal"
    SERVER = "server"
    CLIENT = "client"
    PRODUCER = "producer"
    CONSUMER = "consumer"


@dataclass
class SpanEvent:
    """Event within a span."""
    event_id: str
    name: str
    timestamp: str
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "event_id": self.event_id,
            "name": self.name,
            "timestamp": self.timestamp,
            "attributes": self.attributes,
        }


@dataclass
class Span:
    """Distributed tracing span."""
    span_id: str
    trace_id: str
    parent_span_id: Optional[str]
    name: str
    kind: SpanKind
    start_time: str
    end_time: Optional[str] = None
    status: SpanStatus = SpanStatus.UNSET
    attributes: Dict[str, Any] = field(default_factory=dict)
    events: List[SpanEvent] = field(default_factory=list)
    error_message: Optional[str] = None
    
    @property
    def duration_ms(self) -> Optional[int]:
        """Calculate span duration in milliseconds."""
        if not self.end_time:
            return None
        
        start = datetime.fromisoformat(self.start_time.replace('Z', '+00:00'))
        end = datetime.fromisoformat(self.end_time.replace('Z', '+00:00'))
        
        return int((end - start).total_seconds() * 1000)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "span_id": self.span_id,
            "trace_id": self.trace_id,
            "parent_span_id": self.parent_span_id,
            "name": self.name,
            "kind": self.kind.value,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "duration_ms": self.duration_ms,
            "status": self.status.value,
            "attributes": self.attributes,
            "events": [e.to_dict() for e in self.events],
            "error_message": self.error_message,
        }


@dataclass
class Trace:
    """Complete trace with all spans."""
    trace_id: str
    root_span_id: str
    spans: Dict[str, Span] = field(default_factory=dict)
    start_time: Optional[str] = None
    end_time: Optional[str] = None
    attributes: Dict[str, Any] = field(default_factory=dict)
    
    @property
    def duration_ms(self) -> Optional[int]:
        """Calculate trace duration."""
        if not self.spans:
            return None
        
        starts = []
        ends = []
        
        for span in self.spans.values():
            starts.append(span.start_time)
            if span.end_time:
                ends.append(span.end_time)
        
        if not ends:
            return None
        
        start = min(datetime.fromisoformat(s.replace('Z', '+00:00')) for s in starts)
        end = max(datetime.fromisoformat(e.replace('Z', '+00:00')) for e in ends)
        
        return int((end - start).total_seconds() * 1000)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "root_span_id": self.root_span_id,
            "spans": [s.to_dict() for s in self.spans.values()],
            "span_count": len(self.spans),
            "duration_ms": self.duration_ms,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "attributes": self.attributes,
        }


class SpanExporter:
    """Interface for trace exporters."""
    
    def export(self, trace: Trace) -> bool:
        raise NotImplementedError
    
    def flush(self) -> None:
        raise NotImplementedError
    
    def close(self) -> None:
        raise NotImplementedError


class ConsoleSpanExporter(SpanExporter):
    """Export traces to console."""
    
    def export(self, trace: Trace) -> bool:
        trace_dict = trace.to_dict()
        print(f"[TRACE] {trace.trace_id} - {len(trace.spans)} spans, {trace.duration_ms}ms")
        for span in trace.spans.values():
            status_icon = "✓" if span.status == SpanStatus.OK else "✗" if span.status == SpanStatus.ERROR else "?"
            print(f"  [{status_icon}] {span.name}: {span.duration_ms}ms")
        return True
    
    def flush(self) -> None:
        pass
    
    def close(self) -> None:
        pass


class TracingEngine:
    """Distributed tracing engine."""
    
    def __init__(self, sample_rate: float = 1.0):
        self._sample_rate = sample_rate
        self._traces: Dict[str, Trace] = {}
        self._active_spans: Dict[str, Span] = {}  # span_id -> Span
        self._context: Dict[str, str] = {}  # thread-local context
        self._exporters: List[SpanExporter] = []
        self._lock = threading.Lock()
        
        # Statistics
        self._stats = {
            "total_traces": 0,
            "total_spans": 0,
            "sampled_traces": 0,
            "dropped_traces": 0,
            "exported_traces": 0,
            "failed_exports": 0,
            "by_span_kind": {},
            "by_status": {},
        }
    
    def set_sample_rate(self, rate: float) -> None:
        """Set sampling rate (0.0-1.0)."""
        self._sample_rate = max(0.0, min(1.0, rate))
    
    def add_exporter(self, exporter: SpanExporter) -> None:
        """Add a trace exporter."""
        self._exporters.append(exporter)
        logger.info("Span exporter added: %s", type(exporter).__name__)
    
    def remove_exporter(self, exporter: SpanExporter) -> bool:
        """Remove a trace exporter."""
        if exporter in self._exporters:
            self._exporters.remove(exporter)
            return True
        return False
    
    def start_trace(self, name: str,
                   kind: SpanKind = SpanKind.INTERNAL,
                   attributes: Optional[Dict[str, Any]] = None,
                   trace_id: Optional[str] = None,
                   parent_span_id: Optional[str] = None) -> Span:
        """Start a new trace with root span."""
        if trace_id is None:
            trace_id = f"trace_{uuid.uuid4().hex[:32]}"
        
        # Check sampling
        if not self._should_sample():
            self._stats["dropped_traces"] += 1
            # Return a no-op span
            return self._create_noop_span(trace_id)
        
        span_id = f"span_{uuid.uuid4().hex[:16]}"
        start_time = datetime.now(timezone.utc).isoformat()
        
        span = Span(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            name=name,
            kind=kind,
            start_time=start_time,
            attributes=attributes or {},
        )
        
        # Create trace
        trace = Trace(
            trace_id=trace_id,
            root_span_id=span_id,
            start_time=start_time,
        )
        
        with self._lock:
            self._traces[trace_id] = trace
            self._traces[trace_id].spans[span_id] = span
            self._active_spans[span_id] = span
        
        # Set context
        self._context["trace_id"] = trace_id
        self._context["span_id"] = span_id
        
        # Update stats
        self._stats["total_traces"] += 1
        self._stats["sampled_traces"] += 1
        self._stats["total_spans"] += 1
        self._stats["by_span_kind"][kind.value] = self._stats["by_span_kind"].get(kind.value, 0) + 1
        
        logger.debug("Trace started: %s (span: %s)", trace_id, span_id)
        
        return span
    
    def start_span(self, name: str,
                  kind: SpanKind = SpanKind.INTERNAL,
                  attributes: Optional[Dict[str, Any]] = None,
                  parent_span_id: Optional[str] = None) -> Span:
        """Start a new child span within current trace."""
        # Get current context
        trace_id = self._context.get("trace_id")
        current_span_id = self._context.get("span_id")
        
        if not trace_id:
            # No active trace, start new one
            return self.start_trace(name, kind, attributes)
        
        if parent_span_id is None:
            parent_span_id = current_span_id
        
        span_id = f"span_{uuid.uuid4().hex[:16]}"
        start_time = datetime.now(timezone.utc).isoformat()
        
        span = Span(
            span_id=span_id,
            trace_id=trace_id,
            parent_span_id=parent_span_id,
            name=name,
            kind=kind,
            start_time=start_time,
            attributes=attributes or {},
        )
        
        with self._lock:
            if trace_id in self._traces:
                self._traces[trace_id].spans[span_id] = span
            self._active_spans[span_id] = span
        
        # Update context
        self._context["span_id"] = span_id
        
        # Update stats
        self._stats["total_spans"] += 1
        self._stats["by_span_kind"][kind.value] = self._stats["by_span_kind"].get(kind.value, 0) + 1
        
        return span
    
    def end_span(self, span: Span,
                status: SpanStatus = SpanStatus.OK,
                error_message: Optional[str] = None) -> None:
        """End a span."""
        span.end_time = datetime.now(timezone.utc).isoformat()
        span.status = status
        span.error_message = error_message
        
        with self._lock:
            if span.span_id in self._active_spans:
                del self._active_spans[span.span_id]
        
        # Update stats
        self._stats["by_status"][status.value] = self._stats["by_status"].get(status.value, 0) + 1
        
        # Check if trace is complete
        self._check_trace_complete(span.trace_id)
        
        logger.debug("Span ended: %s (%sms)", span.span_id, span.duration_ms)
    
    def end_trace(self, status: SpanStatus = SpanStatus.OK) -> None:
        """End the current trace."""
        span_id = self._context.get("span_id")
        
        if span_id and span_id in self._active_spans:
            self.end_span(self._active_spans[span_id], status)
        
        # Clear context
        self._context.pop("trace_id", None)
        self._context.pop("span_id", None)
    
    def set_attribute(self, span: Span, key: str, value: Any) -> None:
        """Set span attribute."""
        span.attributes[key] = value
    
    def add_event(self, span: Span, name: str,
                 attributes: Optional[Dict[str, Any]] = None) -> str:
        """Add event to span."""
        event_id = f"event_{uuid.uuid4().hex[:8]}"
        
        event = SpanEvent(
            event_id=event_id,
            name=name,
            timestamp=datetime.now(timezone.utc).isoformat(),
            attributes=attributes or {},
        )
        
        span.events.append(event)
        
        return event_id
    
    def record_error(self, span: Span, exception: Exception) -> None:
        """Record exception on span."""
        span.status = SpanStatus.ERROR
        span.error_message = str(exception)
        
        self.add_event(span, "exception", {
            "type": type(exception).__name__,
            "message": str(exception),
        })
    
    def get_trace(self, trace_id: str) -> Optional[Trace]:
        """Get trace by ID."""
        return self._traces.get(trace_id)
    
    def get_span(self, span_id: str) -> Optional[Span]:
        """Get span by ID."""
        return self._active_spans.get(span_id)
    
    def get_current_trace_id(self) -> Optional[str]:
        """Get current trace ID from context."""
        return self._context.get("trace_id")
    
    def get_current_span_id(self) -> Optional[str]:
        """Get current span ID from context."""
        return self._context.get("span_id")
    
    def get_context(self) -> Dict[str, str]:
        """Get current tracing context."""
        return dict(self._context)
    
    def set_context(self, trace_id: str, span_id: str) -> None:
        """Set tracing context (for context propagation)."""
        self._context["trace_id"] = trace_id
        self._context["span_id"] = span_id
    
    def clear_context(self) -> None:
        """Clear tracing context."""
        self._context.clear()
    
    def flush(self) -> int:
        """Flush all completed traces to exporters."""
        exported = 0
        
        with self._lock:
            complete_traces = [
                t for t in self._traces.values()
                if all(s.end_time is not None for s in t.spans.values())
            ]
        
        for trace in complete_traces:
            for exporter in self._exporters:
                try:
                    if exporter.export(trace):
                        exported += 1
                    else:
                        self._stats["failed_exports"] += 1
                except Exception as e:
                    logger.exception("Export failed: %s", e)
                    self._stats["failed_exports"] += 1
        
        if exported > 0:
            self._stats["exported_traces"] += exported
        
        return exported
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get tracing statistics."""
        return {
            **self._stats,
            "active_spans": len(self._active_spans),
            "total_traces_stored": len(self._traces),
            "total_exporters": len(self._exporters),
        }
    
    def get_all_traces(self) -> List[Dict[str, Any]]:
        """Get all traces."""
        return [t.to_dict() for t in self._traces.values()]
    
    def clear_traces(self) -> int:
        """Clear all stored traces."""
        count = len(self._traces)
        self._traces.clear()
        return count
    
    def _should_sample(self) -> bool:
        """Check if trace should be sampled."""
        return random.random() < self._sample_rate
    
    def _create_noop_span(self, trace_id: str) -> Span:
        """Create a no-op span for dropped traces."""
        return Span(
            span_id="noop",
            trace_id=trace_id,
            parent_span_id=None,
            name="noop",
            kind=SpanKind.INTERNAL,
            start_time=datetime.now(timezone.utc).isoformat(),
        )
    
    def _check_trace_complete(self, trace_id: str) -> None:
        """Check if trace is complete and export."""
        if trace_id not in self._traces:
            return
        
        trace = self._traces[trace_id]
        
        # Check if all spans are ended
        if all(s.end_time is not None for s in trace.spans.values()):
            trace.end_time = datetime.now(timezone.utc).isoformat()
            
            # Auto-export if exporters configured
            if self._exporters:
                self.flush()


def create_tracing_engine(sample_rate: float = 1.0) -> TracingEngine:
    """Factory function to create tracing engine."""
    return TracingEngine(sample_rate=sample_rate)
