"""Tests for Tracing Engine — Slice 48."""
import pytest
from copilot_core.tracing.engine import (
    TracingEngine,
    SpanStatus,
    SpanKind,
    Span,
    SpanEvent,
    Trace,
    ConsoleSpanExporter,
    create_tracing_engine,
)
from datetime import datetime, timezone
import time
import io
import sys


class TestTracingEngine:
    """Test tracing engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_tracing_engine()
        assert engine is not None
    
    def test_create_engine_with_sample_rate(self):
        """Test engine creation with sample rate."""
        engine = create_tracing_engine(sample_rate=0.5)
        assert engine._sample_rate == 0.5
    
    def test_start_trace(self):
        """Test starting a trace."""
        engine = TracingEngine()
        
        span = engine.start_trace("test_operation")
        
        assert span is not None
        assert span.trace_id is not None
        assert span.trace_id.startswith("trace_")
        assert span.span_id.startswith("span_")
        assert span.parent_span_id is None
    
    def test_start_trace_with_custom_id(self):
        """Test starting trace with custom trace ID."""
        engine = TracingEngine()
        
        span = engine.start_trace("test", trace_id="trace_custom123")
        
        assert span.trace_id == "trace_custom123"
    
    def test_start_trace_with_attributes(self):
        """Test starting trace with attributes."""
        engine = TracingEngine()
        
        span = engine.start_trace(
            "test_operation",
            attributes={"user_id": "123", "action": "login"},
        )
        
        assert span.attributes["user_id"] == "123"
        assert span.attributes["action"] == "login"
    
    def test_start_trace_with_kind(self):
        """Test starting trace with span kind."""
        engine = TracingEngine()
        
        span = engine.start_trace("http_request", kind=SpanKind.SERVER)
        
        assert span.kind == SpanKind.SERVER
    
    def test_end_span(self):
        """Test ending a span."""
        engine = TracingEngine()
        
        span = engine.start_trace("test")
        
        time.sleep(0.01)  # Small delay
        
        engine.end_span(span, status=SpanStatus.OK)
        
        assert span.end_time is not None
        assert span.status == SpanStatus.OK
        assert span.duration_ms is not None
        assert span.duration_ms >= 10
    
    def test_end_span_with_error(self):
        """Test ending span with error."""
        engine = TracingEngine()
        
        span = engine.start_trace("test")
        
        engine.end_span(
            span,
            status=SpanStatus.ERROR,
            error_message="Something went wrong",
        )
        
        assert span.status == SpanStatus.ERROR
        assert span.error_message == "Something went wrong"
    
    def test_end_trace(self):
        """Test ending a trace."""
        engine = TracingEngine()
        
        engine.start_trace("test")
        
        engine.end_trace(status=SpanStatus.OK)
        
        # Context should be cleared
        assert engine.get_current_trace_id() is None
        assert engine.get_current_span_id() is None
    
    def test_start_span_child(self):
        """Test starting child span."""
        engine = TracingEngine()
        
        root = engine.start_trace("root_operation")
        
        child = engine.start_span("child_operation")
        
        assert child.trace_id == root.trace_id
        assert child.parent_span_id == root.span_id
        assert child.span_id != root.span_id
    
    def test_start_span_nested(self):
        """Test starting nested spans."""
        engine = TracingEngine()
        
        root = engine.start_trace("root")
        child1 = engine.start_span("child1")
        child2 = engine.start_span("child2")
        
        assert child2.parent_span_id == child1.span_id
        assert child1.parent_span_id == root.span_id
    
    def test_set_attribute(self):
        """Test setting span attribute."""
        engine = TracingEngine()
        
        span = engine.start_trace("test")
        
        engine.set_attribute(span, "http.method", "GET")
        engine.set_attribute(span, "http.status_code", 200)
        
        assert span.attributes["http.method"] == "GET"
        assert span.attributes["http.status_code"] == 200
    
    def test_add_event(self):
        """Test adding event to span."""
        engine = TracingEngine()
        
        span = engine.start_trace("test")
        
        event_id = engine.add_event(
            span,
            "request_received",
            attributes={"size": 1024},
        )
        
        assert event_id is not None
        assert event_id.startswith("event_")
        assert len(span.events) == 1
        assert span.events[0].name == "request_received"
        assert span.events[0].attributes["size"] == 1024
    
    def test_record_error(self):
        """Test recording exception on span."""
        engine = TracingEngine()
        
        span = engine.start_trace("test")
        
        try:
            raise ValueError("Test error")
        except Exception as e:
            engine.record_error(span, e)
        
        assert span.status == SpanStatus.ERROR
        assert span.error_message == "Test error"
        assert len(span.events) == 1
        assert span.events[0].name == "exception"
    
    def test_get_trace(self):
        """Test getting trace by ID."""
        engine = TracingEngine()
        
        span = engine.start_trace("test")
        
        trace = engine.get_trace(span.trace_id)
        
        assert trace is not None
        assert trace.trace_id == span.trace_id
    
    def test_get_unknown_trace(self):
        """Test getting unknown trace."""
        engine = TracingEngine()
        
        trace = engine.get_trace("unknown_trace")
        
        assert trace is None
    
    def test_get_span(self):
        """Test getting span by ID."""
        engine = TracingEngine()
        
        span = engine.start_trace("test")
        
        retrieved = engine.get_span(span.span_id)
        
        assert retrieved is not None
        assert retrieved.span_id == span.span_id
    
    def test_get_current_trace_id(self):
        """Test getting current trace ID."""
        engine = TracingEngine()
        
        engine.start_trace("test")
        
        trace_id = engine.get_current_trace_id()
        
        assert trace_id is not None
        assert trace_id.startswith("trace_")
    
    def test_get_current_span_id(self):
        """Test getting current span ID."""
        engine = TracingEngine()
        
        engine.start_trace("test")
        
        span_id = engine.get_current_span_id()
        
        assert span_id is not None
        assert span_id.startswith("span_")
    
    def test_set_context(self):
        """Test setting tracing context."""
        engine = TracingEngine()
        
        engine.set_context("trace_abc", "span_xyz")
        
        assert engine.get_current_trace_id() == "trace_abc"
        assert engine.get_current_span_id() == "span_xyz"
    
    def test_clear_context(self):
        """Test clearing tracing context."""
        engine = TracingEngine()
        
        engine.set_context("trace_abc", "span_xyz")
        engine.clear_context()
        
        assert engine.get_current_trace_id() is None
        assert engine.get_current_span_id() is None
    
    def test_get_context(self):
        """Test getting tracing context."""
        engine = TracingEngine()
        
        engine.set_context("trace_abc", "span_xyz")
        
        context = engine.get_context()
        
        assert context["trace_id"] == "trace_abc"
        assert context["span_id"] == "span_xyz"
    
    def test_add_console_exporter(self):
        """Test adding console exporter."""
        engine = TracingEngine()
        
        exporter = ConsoleSpanExporter()
        engine.add_exporter(exporter)
        
        assert len(engine._exporters) == 1
    
    def test_remove_exporter(self):
        """Test removing exporter."""
        engine = TracingEngine()
        
        exporter = ConsoleSpanExporter()
        engine.add_exporter(exporter)
        
        result = engine.remove_exporter(exporter)
        
        assert result is True
        assert len(engine._exporters) == 0
    
    def test_remove_unknown_exporter(self):
        """Test removing unknown exporter."""
        engine = TracingEngine()
        
        result = engine.remove_exporter(ConsoleSpanExporter())
        
        assert result is False
    
    def test_set_sample_rate(self):
        """Test setting sample rate."""
        engine = TracingEngine()
        
        engine.set_sample_rate(0.1)
        
        assert engine._sample_rate == 0.1
    
    def test_sample_rate_clamped(self):
        """Test that sample rate is clamped to 0-1."""
        engine = TracingEngine()
        
        engine.set_sample_rate(1.5)
        assert engine._sample_rate == 1.0
        
        engine.set_sample_rate(-0.5)
        assert engine._sample_rate == 0.0
    
    def test_sampling_drops_traces(self):
        """Test that sampling drops traces."""
        engine = TracingEngine(sample_rate=0.0)  # 0% sampling
        
        span = engine.start_trace("test")
        
        # Should be a noop span
        assert span.span_id == "noop"
        
        stats = engine.get_statistics()
        assert stats["dropped_traces"] == 1
    
    def test_sampling_all_traces(self):
        """Test sampling all traces."""
        engine = TracingEngine(sample_rate=1.0)  # 100% sampling
        
        for i in range(10):
            engine.start_trace(f"test_{i}")
        
        stats = engine.get_statistics()
        
        assert stats["sampled_traces"] == 10
        assert stats["dropped_traces"] == 0
    
    def test_flush_completed_traces(self):
        """Test flushing completed traces."""
        engine = TracingEngine()
        
        exported = []
        
        class CaptureExporter:
            def export(self, trace):
                exported.append(trace)
                return True
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        engine.add_exporter(CaptureExporter())
        
        # Start and end trace
        span = engine.start_trace("test")
        engine.end_span(span)
        
        count = engine.flush()
        
        assert count >= 1
        assert len(exported) >= 1
    
    def test_flush_incomplete_traces(self):
        """Test that incomplete traces are not flushed."""
        engine = TracingEngine()
        
        exported = []
        
        class CaptureExporter:
            def export(self, trace):
                exported.append(trace)
                return True
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        engine.add_exporter(CaptureExporter())
        
        # Start trace but don't end it
        engine.start_trace("test")
        
        count = engine.flush()
        
        assert count == 0
        assert len(exported) == 0
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = TracingEngine()
        
        span = engine.start_trace("test", kind=SpanKind.SERVER)
        engine.end_span(span, status=SpanStatus.OK)
        
        stats = engine.get_statistics()
        
        assert stats["total_traces"] == 1
        assert stats["total_spans"] == 1
        assert stats["sampled_traces"] == 1
        assert stats["by_span_kind"]["server"] == 1
        assert stats["by_status"]["ok"] == 1
    
    def test_statistics_active_spans(self):
        """Test that statistics track active spans."""
        engine = TracingEngine()
        
        engine.start_trace("test1")
        engine.start_span("child1")
        engine.start_span("child2")
        
        stats = engine.get_statistics()
        
        assert stats["active_spans"] == 3
    
    def test_statistics_exported_traces(self):
        """Test that statistics track exported traces."""
        engine = TracingEngine()
        
        class SuccessExporter:
            def export(self, trace):
                return True
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        engine.add_exporter(SuccessExporter())
        
        span = engine.start_trace("test")
        engine.end_span(span)
        engine.flush()
        
        stats = engine.get_statistics()
        
        assert stats["exported_traces"] >= 1
    
    def test_statistics_failed_exports(self):
        """Test that statistics track failed exports."""
        engine = TracingEngine()
        
        class FailingExporter:
            def export(self, trace):
                raise Exception("Export failed")
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        engine.add_exporter(FailingExporter())
        
        span = engine.start_trace("test")
        engine.end_span(span)
        engine.flush()
        
        stats = engine.get_statistics()
        
        assert stats["failed_exports"] >= 1
    
    def test_get_all_traces(self):
        """Test getting all traces."""
        engine = TracingEngine()
        
        engine.start_trace("trace1")
        engine.start_trace("trace2")
        engine.start_trace("trace3")
        
        traces = engine.get_all_traces()
        
        assert len(traces) == 3
    
    def test_clear_traces(self):
        """Test clearing all traces."""
        engine = TracingEngine()
        
        engine.start_trace("trace1")
        engine.start_trace("trace2")
        
        count = engine.clear_traces()
        
        assert count == 2
        assert len(engine._traces) == 0
    
    def test_span_to_dict(self):
        """Test span serialization."""
        span = Span(
            span_id="span_test",
            trace_id="trace_test",
            parent_span_id=None,
            name="test_span",
            kind=SpanKind.SERVER,
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-01T00:00:01Z",
            status=SpanStatus.OK,
        )
        
        d = span.to_dict()
        
        assert d["span_id"] == "span_test"
        assert d["trace_id"] == "trace_test"
        assert d["kind"] == "server"
        assert d["duration_ms"] == 1000
    
    def test_span_duration_calculation(self):
        """Test span duration calculation."""
        span = Span(
            span_id="span_test",
            trace_id="trace_test",
            parent_span_id=None,
            name="test",
            kind=SpanKind.INTERNAL,
            start_time="2025-01-01T00:00:00.000000Z",
            end_time="2025-01-01T00:00:00.500000Z",
        )
        
        assert span.duration_ms == 500
    
    def test_span_duration_none_when_not_ended(self):
        """Test that duration is None when span not ended."""
        span = Span(
            span_id="span_test",
            trace_id="trace_test",
            parent_span_id=None,
            name="test",
            kind=SpanKind.INTERNAL,
            start_time="2025-01-01T00:00:00Z",
        )
        
        assert span.duration_ms is None
    
    def test_span_event_to_dict(self):
        """Test span event serialization."""
        event = SpanEvent(
            event_id="event_test",
            name="request_received",
            timestamp="2025-01-01T00:00:00Z",
            attributes={"size": 1024},
        )
        
        d = event.to_dict()
        
        assert d["event_id"] == "event_test"
        assert d["name"] == "request_received"
        assert d["attributes"]["size"] == 1024
    
    def test_trace_to_dict(self):
        """Test trace serialization."""
        trace = Trace(
            trace_id="trace_test",
            root_span_id="span_root",
        )
        
        span = Span(
            span_id="span_root",
            trace_id="trace_test",
            parent_span_id=None,
            name="root",
            kind=SpanKind.INTERNAL,
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-01T00:00:01Z",
        )
        trace.spans["span_root"] = span
        
        d = trace.to_dict()
        
        assert d["trace_id"] == "trace_test"
        assert d["root_span_id"] == "span_root"
        assert d["span_count"] == 1
        assert d["duration_ms"] == 1000
    
    def test_trace_duration_calculation(self):
        """Test trace duration calculation."""
        trace = Trace(
            trace_id="trace_test",
            root_span_id="span_root",
        )
        
        # Root span: 0-100ms
        root = Span(
            span_id="span_root",
            trace_id="trace_test",
            parent_span_id=None,
            name="root",
            kind=SpanKind.INTERNAL,
            start_time="2025-01-01T00:00:00.000000Z",
            end_time="2025-01-01T00:00:00.100000Z",
        )
        
        # Child span: 20-80ms (within root)
        child = Span(
            span_id="span_child",
            trace_id="trace_test",
            parent_span_id="span_root",
            name="child",
            kind=SpanKind.INTERNAL,
            start_time="2025-01-01T00:00:00.020000Z",
            end_time="2025-01-01T00:00:00.080000Z",
        )
        
        trace.spans["span_root"] = root
        trace.spans["span_child"] = child
        
        # Trace duration should be root span duration
        assert trace.duration_ms == 100
    
    def test_trace_duration_none_when_no_spans(self):
        """Test that trace duration is None when no spans."""
        trace = Trace(
            trace_id="trace_test",
            root_span_id="span_root",
        )
        
        assert trace.duration_ms is None
    
    def test_span_status_enum_values(self):
        """Test span status enum values."""
        assert SpanStatus.UNSET.value == "unset"
        assert SpanStatus.OK.value == "ok"
        assert SpanStatus.ERROR.value == "error"
    
    def test_span_kind_enum_values(self):
        """Test span kind enum values."""
        assert SpanKind.INTERNAL.value == "internal"
        assert SpanKind.SERVER.value == "server"
        assert SpanKind.CLIENT.value == "client"
        assert SpanKind.PRODUCER.value == "producer"
        assert SpanKind.CONSUMER.value == "consumer"
    
    def test_console_exporter(self):
        """Test console exporter."""
        exporter = ConsoleSpanExporter()
        
        trace = Trace(
            trace_id="trace_test",
            root_span_id="span_root",
        )
        
        span = Span(
            span_id="span_root",
            trace_id="trace_test",
            parent_span_id=None,
            name="test",
            kind=SpanKind.INTERNAL,
            start_time="2025-01-01T00:00:00Z",
            end_time="2025-01-01T00:00:01Z",
        )
        trace.spans["span_root"] = span
        
        # Should not raise
        result = exporter.export(trace)
        
        assert result is True
        
        exporter.flush()
        exporter.close()
    
    def test_multiple_child_spans(self):
        """Test multiple child spans under same parent."""
        engine = TracingEngine()
        
        root = engine.start_trace("root")
        
        child1 = engine.start_span("child1")
        engine.end_span(child1)
        
        child2 = engine.start_span("child2")
        engine.end_span(child2)
        
        child3 = engine.start_span("child3")
        engine.end_span(child3)
        
        trace = engine.get_trace(root.trace_id)
        
        assert len(trace.spans) == 4  # root + 3 children
    
    def test_span_attributes_preserved(self):
        """Test that span attributes are preserved."""
        engine = TracingEngine()
        
        span = engine.start_trace(
            "test",
            attributes={
                "http.method": "POST",
                "http.url": "/api/users",
                "http.status_code": 201,
                "user.id": "123",
            },
        )
        
        assert span.attributes["http.method"] == "POST"
        assert span.attributes["http.url"] == "/api/users"
        assert span.attributes["http.status_code"] == 201
        assert span.attributes["user.id"] == "123"
    
    def test_events_preserved_order(self):
        """Test that events preserve order."""
        engine = TracingEngine()
        
        span = engine.start_trace("test")
        
        engine.add_event(span, "first")
        engine.add_event(span, "second")
        engine.add_event(span, "third")
        
        assert span.events[0].name == "first"
        assert span.events[1].name == "second"
        assert span.events[2].name == "third"
    
    def test_parent_span_id_override(self):
        """Test overriding parent span ID."""
        engine = TracingEngine()
        
        root = engine.start_trace("root")
        child1 = engine.start_span("child1")
        
        # Start child2 with explicit parent (skip child1)
        child2 = engine.start_span("child2", parent_span_id=root.span_id)
        
        assert child2.parent_span_id == root.span_id
        assert child1.parent_span_id == root.span_id
    
    def test_trace_attributes(self):
        """Test trace attributes."""
        engine = TracingEngine()
        
        engine.start_trace("test")
        
        trace_id = engine.get_current_trace_id()
        trace = engine.get_trace(trace_id)
        
        trace.attributes["service.name"] = "test-service"
        trace.attributes["deployment.environment"] = "production"
        
        assert trace.attributes["service.name"] == "test-service"
    
    def test_noop_span_operations(self):
        """Test operations on noop span."""
        engine = TracingEngine(sample_rate=0.0)
        
        span = engine.start_trace("test")
        
        # Should not raise on noop span
        engine.set_attribute(span, "key", "value")
        engine.add_event(span, "test_event")
        
        try:
            raise ValueError("test")
        except Exception as e:
            engine.record_error(span, e)
        
        engine.end_span(span)
    
    def test_statistics_by_span_kind(self):
        """Test statistics breakdown by span kind."""
        engine = TracingEngine()
        
        engine.start_trace("server", kind=SpanKind.SERVER)
        engine.start_trace("client", kind=SpanKind.CLIENT)
        engine.start_trace("internal", kind=SpanKind.INTERNAL)
        
        stats = engine.get_statistics()
        
        assert stats["by_span_kind"]["server"] == 1
        assert stats["by_span_kind"]["client"] == 1
        assert stats["by_span_kind"]["internal"] == 1
    
    def test_statistics_by_status(self):
        """Test statistics breakdown by status."""
        engine = TracingEngine()
        
        span1 = engine.start_trace("ok")
        engine.end_span(span1, status=SpanStatus.OK)
        
        span2 = engine.start_trace("error")
        engine.end_span(span2, status=SpanStatus.ERROR)
        
        span3 = engine.start_trace("unset")
        # Don't end span3 - should remain unset
        
        stats = engine.get_statistics()
        
        assert stats["by_status"]["ok"] == 1
        assert stats["by_status"]["error"] == 1
    
    def test_total_traces_stored(self):
        """Test that statistics track total traces stored."""
        engine = TracingEngine()
        
        engine.start_trace("trace1")
        engine.start_trace("trace2")
        engine.start_trace("trace3")
        
        stats = engine.get_statistics()
        
        assert stats["total_traces_stored"] == 3
    
    def test_total_exporters(self):
        """Test that statistics track total exporters."""
        engine = TracingEngine()
        
        engine.add_exporter(ConsoleSpanExporter())
        engine.add_exporter(ConsoleSpanExporter())
        
        stats = engine.get_statistics()
        
        assert stats["total_exporters"] == 2
    
    def test_span_id_unique(self):
        """Test that span IDs are unique."""
        engine = TracingEngine()
        
        ids = set()
        for i in range(100):
            span = engine.start_trace(f"test_{i}")
            ids.add(span.span_id)
        
        assert len(ids) == 100
    
    def test_trace_id_unique(self):
        """Test that trace IDs are unique."""
        engine = TracingEngine()
        
        ids = set()
        for i in range(100):
            span = engine.start_trace(f"test_{i}")
            ids.add(span.trace_id)
        
        assert len(ids) == 100
    
    def test_event_id_unique(self):
        """Test that event IDs are unique."""
        engine = TracingEngine()
        
        span = engine.start_trace("test")
        
        ids = set()
        for i in range(100):
            event_id = engine.add_event(span, f"event_{i}")
            ids.add(event_id)
        
        assert len(ids) == 100
    
    def test_start_span_without_active_trace(self):
        """Test starting span without active trace creates new trace."""
        engine = TracingEngine()
        
        # No active trace
        span = engine.start_span("orphan_span")
        
        # Should have created a new trace
        assert span.trace_id is not None
        assert span.parent_span_id is None
    
    def test_context_isolation(self):
        """Test that context is properly isolated."""
        engine = TracingEngine()
        
        engine.start_trace("trace1")
        trace1_id = engine.get_current_trace_id()
        span1_id = engine.get_current_span_id()
        
        engine.start_span("child1")
        child1_id = engine.get_current_span_id()
        
        # Child should have same trace, different span
        assert engine.get_current_trace_id() == trace1_id
        assert engine.get_current_span_id() == child1_id
        assert child1_id != span1_id
    
    def test_exception_attributes_in_record_error(self):
        """Test that exception attributes are recorded."""
        engine = TracingEngine()
        
        span = engine.start_trace("test")
        
        try:
            raise ValueError("Something went wrong")
        except Exception as e:
            engine.record_error(span, e)
        
        exception_event = span.events[0]
        
        assert exception_event.attributes["type"] == "ValueError"
        assert exception_event.attributes["message"] == "Something went wrong"
    
    def test_trace_with_no_ended_spans(self):
        """Test trace duration when no spans ended."""
        trace = Trace(
            trace_id="trace_test",
            root_span_id="span_root",
        )
        
        span = Span(
            span_id="span_root",
            trace_id="trace_test",
            parent_span_id=None,
            name="root",
            kind=SpanKind.INTERNAL,
            start_time="2025-01-01T00:00:00Z",
            # No end_time
        )
        trace.spans["span_root"] = span
        
        assert trace.duration_ms is None
    
    def test_exporter_exception_handled(self):
        """Test that exporter exceptions are handled gracefully."""
        engine = TracingEngine()
        
        call_count = [0]
        
        class FlakyExporter:
            def export(self, trace):
                call_count[0] += 1
                if call_count[0] == 1:
                    raise Exception("First call fails")
                return True
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        engine.add_exporter(FlakyExporter())
        
        span = engine.start_trace("test")
        engine.end_span(span)
        
        # Should not raise
        engine.flush()
    
    def test_span_kind_stored_in_stats(self):
        """Test that span kind is stored in statistics."""
        engine = TracingEngine()
        
        for kind in SpanKind:
            span = engine.start_trace(f"test_{kind.value}", kind=kind)
            engine.end_span(span)
        
        stats = engine.get_statistics()
        
        assert stats["by_span_kind"]["internal"] == 1
        assert stats["by_span_kind"]["server"] == 1
        assert stats["by_span_kind"]["client"] == 1
        assert stats["by_span_kind"]["producer"] == 1
        assert stats["by_span_kind"]["consumer"] == 1
