"""Tests for Logging Engine — Slice 47."""
import pytest
from copilot_core.logging.engine import (
    LoggingEngine,
    LogLevel,
    LogFormat,
    LogEntry,
    LogBuffer,
    LogFilter,
    ConsoleLogWriter,
    FileLogWriter,
    AsyncLogWriter,
    create_logging_engine,
)
from datetime import datetime, timezone
import io
import sys
import tempfile
import os
import time


class TestLoggingEngine:
    """Test logging engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_logging_engine()
        assert engine is not None
    
    def test_create_engine_with_level(self):
        """Test engine creation with log level."""
        engine = create_logging_engine(level=LogLevel.DEBUG)
        assert engine._default_level == LogLevel.DEBUG
    
    def test_create_engine_with_format(self):
        """Test engine creation with log format."""
        engine = create_logging_engine(format=LogFormat.TEXT)
        assert engine._default_format == LogFormat.TEXT
    
    def test_log_info(self):
        """Test logging INFO message."""
        engine = LoggingEngine()
        
        entry_id = engine.info("Test message")
        
        assert entry_id is not None
        assert entry_id.startswith("log_")
    
    def test_log_debug(self):
        """Test logging DEBUG message."""
        engine = LoggingEngine()
        
        entry_id = engine.debug("Debug message")
        
        assert entry_id is not None
    
    def test_log_warning(self):
        """Test logging WARNING message."""
        engine = LoggingEngine()
        
        entry_id = engine.warning("Warning message")
        
        assert entry_id is not None
    
    def test_log_error(self):
        """Test logging ERROR message."""
        engine = LoggingEngine()
        
        entry_id = engine.error("Error message")
        
        assert entry_id is not None
    
    def test_log_critical(self):
        """Test logging CRITICAL message."""
        engine = LoggingEngine()
        
        entry_id = engine.critical("Critical message")
        
        assert entry_id is not None
    
    def test_log_with_logger_name(self):
        """Test logging with logger name."""
        engine = LoggingEngine()
        
        engine.info("Test", logger_name="test.logger")
        
        stats = engine.get_statistics()
        
        assert "test.logger" in stats["by_logger"]
    
    def test_log_with_extra(self):
        """Test logging with extra data."""
        engine = LoggingEngine()
        
        # Add writer to capture
        output = io.StringIO()
        
        class CaptureWriter:
            def __init__(self, out):
                self.out = out
                self.last_entry = None
            
            def write(self, entry):
                self.last_entry = entry
                self.out.write(entry.to_json() + "\n")
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        writer = CaptureWriter(output)
        engine.add_writer(writer)
        
        engine.info("Test", extra={"user_id": "123", "action": "login"})
        
        assert writer.last_entry is not None
        assert writer.last_entry.extra["user_id"] == "123"
        assert writer.last_entry.extra["action"] == "login"
    
    def test_log_with_exception(self):
        """Test logging with exception."""
        engine = LoggingEngine()
        
        output = io.StringIO()
        
        class CaptureWriter:
            def __init__(self, out):
                self.out = out
                self.last_entry = None
            
            def write(self, entry):
                self.last_entry = entry
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        writer = CaptureWriter(output)
        engine.add_writer(writer)
        
        try:
            raise ValueError("Test error")
        except Exception as e:
            engine.exception("Something failed", exc=e)
        
        assert writer.last_entry is not None
        assert writer.last_entry.exception is not None
        assert "Test error" in writer.last_entry.exception
    
    def test_log_with_source_info(self):
        """Test logging with source file and line."""
        engine = LoggingEngine()
        
        output = io.StringIO()
        
        class CaptureWriter:
            def __init__(self, out):
                self.out = out
                self.last_entry = None
            
            def write(self, entry):
                self.last_entry = entry
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        writer = CaptureWriter(output)
        engine.add_writer(writer)
        
        engine.info("Test", source_file="test.py", source_line=42)
        
        assert writer.last_entry.source_file == "test.py"
        assert writer.last_entry.source_line == 42
    
    def test_set_context(self):
        """Test setting global context."""
        engine = LoggingEngine()
        
        engine.set_context("request_id", "req_123")
        engine.set_context("user_id", "user_456")
        
        context = engine.get_context()
        
        assert context["request_id"] == "req_123"
        assert context["user_id"] == "user_456"
    
    def test_context_included_in_log(self):
        """Test that context is included in log entries."""
        engine = LoggingEngine()
        
        engine.set_context("session_id", "sess_abc")
        
        output = io.StringIO()
        
        class CaptureWriter:
            def __init__(self, out):
                self.out = out
                self.last_entry = None
            
            def write(self, entry):
                self.last_entry = entry
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        writer = CaptureWriter(output)
        engine.add_writer(writer)
        
        engine.info("Test message")
        
        assert writer.last_entry.context["session_id"] == "sess_abc"
    
    def test_clear_context_key(self):
        """Test clearing specific context key."""
        engine = LoggingEngine()
        
        engine.set_context("key1", "value1")
        engine.set_context("key2", "value2")
        
        engine.clear_context("key1")
        
        context = engine.get_context()
        
        assert "key1" not in context
        assert "key2" in context
    
    def test_clear_all_context(self):
        """Test clearing all context."""
        engine = LoggingEngine()
        
        engine.set_context("key1", "value1")
        engine.set_context("key2", "value2")
        
        engine.clear_context()
        
        context = engine.get_context()
        
        assert context == {}
    
    def test_add_console_writer(self):
        """Test adding console writer."""
        engine = LoggingEngine()
        
        writer = ConsoleLogWriter()
        engine.add_writer(writer)
        
        assert len(engine._writers) == 1
    
    def test_remove_writer(self):
        """Test removing writer."""
        engine = LoggingEngine()
        
        writer = ConsoleLogWriter()
        engine.add_writer(writer)
        
        result = engine.remove_writer(writer)
        
        assert result is True
        assert len(engine._writers) == 0
    
    def test_remove_unknown_writer(self):
        """Test removing unknown writer."""
        engine = LoggingEngine()
        
        result = engine.remove_writer(ConsoleLogWriter())
        
        assert result is False
    
    def test_add_filter(self):
        """Test adding log filter."""
        engine = LoggingEngine()
        
        filter = LogFilter(
            filter_id="filter_test",
            name="Test Filter",
            min_level=LogLevel.WARNING,
        )
        
        filter_id = engine.add_filter(filter)
        
        assert filter_id == "filter_test"
    
    def test_remove_filter(self):
        """Test removing filter."""
        engine = LoggingEngine()
        
        filter = LogFilter(filter_id="f1", name="Test")
        engine.add_filter(filter)
        
        result = engine.remove_filter("f1")
        
        assert result is True
    
    def test_remove_unknown_filter(self):
        """Test removing unknown filter."""
        engine = LoggingEngine()
        
        result = engine.remove_filter("unknown")
        
        assert result is False
    
    def test_filter_by_level(self):
        """Test filtering by log level."""
        engine = LoggingEngine()
        
        filter = LogFilter(
            filter_id="f1",
            name="Warning Only",
            min_level=LogLevel.WARNING,
        )
        engine.add_filter(filter)
        
        output = io.StringIO()
        
        class CaptureWriter:
            def __init__(self, out):
                self.out = out
                self.entries = []
            
            def write(self, entry):
                self.entries.append(entry)
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        writer = CaptureWriter(output)
        engine.add_writer(writer)
        
        engine.debug("Debug")  # Should be filtered
        engine.info("Info")    # Should be filtered
        engine.warning("Warn") # Should pass
        engine.error("Error")  # Should pass
        
        assert len(writer.entries) == 2
    
    def test_filter_by_logger_include(self):
        """Test filtering by logger include."""
        engine = LoggingEngine()
        
        filter = LogFilter(
            filter_id="f1",
            name="Include API",
            include_loggers=["api"],
        )
        engine.add_filter(filter)
        
        output = io.StringIO()
        
        class CaptureWriter:
            def __init__(self, out):
                self.out = out
                self.entries = []
            
            def write(self, entry):
                self.entries.append(entry)
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        writer = CaptureWriter(output)
        engine.add_writer(writer)
        
        engine.info("API message", logger_name="api.service")
        engine.info("DB message", logger_name="db.service")
        
        assert len(writer.entries) == 1
        assert writer.entries[0].logger_name == "api.service"
    
    def test_filter_by_logger_exclude(self):
        """Test filtering by logger exclude."""
        engine = LoggingEngine()
        
        filter = LogFilter(
            filter_id="f1",
            name="Exclude Health",
            exclude_loggers=["health"],
        )
        engine.add_filter(filter)
        
        output = io.StringIO()
        
        class CaptureWriter:
            def __init__(self, out):
                self.out = out
                self.entries = []
            
            def write(self, entry):
                self.entries.append(entry)
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        writer = CaptureWriter(output)
        engine.add_writer(writer)
        
        engine.info("API message", logger_name="api.service")
        engine.info("Health check", logger_name="health.check")
        
        assert len(writer.entries) == 1
        assert writer.entries[0].logger_name == "api.service"
    
    def test_filter_by_pattern_include(self):
        """Test filtering by pattern include."""
        engine = LoggingEngine()
        
        filter = LogFilter(
            filter_id="f1",
            name="Include Errors",
            include_patterns=["error", "fail"],
        )
        engine.add_filter(filter)
        
        output = io.StringIO()
        
        class CaptureWriter:
            def __init__(self, out):
                self.out = out
                self.entries = []
            
            def write(self, entry):
                self.entries.append(entry)
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        writer = CaptureWriter(output)
        engine.add_writer(writer)
        
        engine.info("Something failed")
        engine.info("All good")
        engine.info("Error occurred")
        
        assert len(writer.entries) == 2
    
    def test_filter_by_pattern_exclude(self):
        """Test filtering by pattern exclude."""
        engine = LoggingEngine()
        
        filter = LogFilter(
            filter_id="f1",
            name="Exclude Health",
            exclude_patterns=["health", "heartbeat"],
        )
        engine.add_filter(filter)
        
        output = io.StringIO()
        
        class CaptureWriter:
            def __init__(self, out):
                self.out = out
                self.entries = []
            
            def write(self, entry):
                self.entries.append(entry)
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        writer = CaptureWriter(output)
        engine.add_writer(writer)
        
        engine.info("Health check OK")
        engine.info("User logged in")
        engine.info("Heartbeat received")
        
        assert len(writer.entries) == 1
        assert "User logged in" in writer.entries[0].message
    
    def test_filter_sampling(self):
        """Test filter sampling."""
        engine = LoggingEngine()
        
        # 50% sample rate
        filter = LogFilter(
            filter_id="f1",
            name="Sample 50%",
            sample_rate=0.5,
        )
        engine.add_filter(filter)
        
        output = io.StringIO()
        
        class CaptureWriter:
            def __init__(self, out):
                self.out = out
                self.entries = []
            
            def write(self, entry):
                self.entries.append(entry)
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        writer = CaptureWriter(output)
        engine.add_writer(writer)
        
        # Log 100 messages
        for i in range(100):
            engine.info(f"Message {i}")
        
        # Should be roughly 50 (allow variance)
        assert 30 <= len(writer.entries) <= 70
    
    def test_create_buffer(self):
        """Test creating log buffer."""
        engine = LoggingEngine()
        
        buffer_id = engine.create_buffer("test_buffer", max_size=100)
        
        assert buffer_id is not None
        assert buffer_id.startswith("buf_")
    
    def test_get_buffer(self):
        """Test getting buffer."""
        engine = LoggingEngine()
        
        buffer_id = engine.create_buffer("test")
        
        buffer = engine.get_buffer(buffer_id)
        
        assert buffer is not None
        assert buffer.max_size == 100
    
    def test_get_unknown_buffer(self):
        """Test getting unknown buffer."""
        engine = LoggingEngine()
        
        buffer = engine.get_buffer("unknown")
        
        assert buffer is None
    
    def test_buffer_add_entry(self):
        """Test adding entry to buffer."""
        engine = LoggingEngine()
        
        buffer_id = engine.create_buffer("test", max_size=10)
        
        entry_id = engine.info("Test message", buffer_id=buffer_id)
        
        buffer = engine.get_buffer(buffer_id)
        
        assert buffer.size() == 1
    
    def test_buffer_max_size(self):
        """Test buffer max size enforcement."""
        engine = LoggingEngine()
        
        buffer_id = engine.create_buffer("test", max_size=5)
        
        for i in range(10):
            engine.info(f"Message {i}", buffer_id=buffer_id)
        
        buffer = engine.get_buffer(buffer_id)
        
        assert buffer.size() == 5
    
    def test_drain_buffer(self):
        """Test draining buffer."""
        engine = LoggingEngine()
        
        buffer_id = engine.create_buffer("test", max_size=10)
        
        for i in range(5):
            engine.info(f"Message {i}", buffer_id=buffer_id)
        
        entries = engine.drain_buffer(buffer_id)
        
        assert len(entries) == 5
        
        buffer = engine.get_buffer(buffer_id)
        assert buffer.size() == 0
    
    def test_drain_unknown_buffer(self):
        """Test draining unknown buffer."""
        engine = LoggingEngine()
        
        entries = engine.drain_buffer("unknown")
        
        assert entries == []
    
    def test_log_entry_to_dict(self):
        """Test log entry serialization."""
        entry = LogEntry(
            entry_id="log_test",
            level=LogLevel.INFO,
            message="Test message",
            timestamp="2025-01-01T00:00:00Z",
            logger_name="test",
            context={"key": "value"},
            extra={"extra_key": "extra_value"},
        )
        
        d = entry.to_dict()
        
        assert d["entry_id"] == "log_test"
        assert d["level"] == 20
        assert d["level_name"] == "INFO"
        assert d["message"] == "Test message"
    
    def test_log_entry_to_json(self):
        """Test log entry JSON serialization."""
        entry = LogEntry(
            entry_id="log_test",
            level=LogLevel.INFO,
            message="Test message",
            timestamp="2025-01-01T00:00:00Z",
            logger_name="test",
        )
        
        json_str = entry.to_json()
        
        assert "log_test" in json_str
        assert "Test message" in json_str
    
    def test_log_filter_to_dict(self):
        """Test log filter serialization."""
        filter = LogFilter(
            filter_id="f1",
            name="Test Filter",
            min_level=LogLevel.WARNING,
            include_loggers=["api"],
            sample_rate=0.5,
        )
        
        d = filter.to_dict()
        
        assert d["filter_id"] == "f1"
        assert d["name"] == "Test Filter"
        assert d["min_level"] == 30
        assert d["include_loggers"] == ["api"]
        assert d["sample_rate"] == 0.5
    
    def test_log_buffer_to_dict_via_get(self):
        """Test log buffer access."""
        buffer = LogBuffer(max_size=100)
        
        assert buffer.max_size == 100
        assert buffer.size() == 0
    
    def test_console_writer_json_format(self):
        """Test console writer with JSON format."""
        writer = ConsoleLogWriter(format=LogFormat.JSON)
        
        entry = LogEntry(
            entry_id="log_test",
            level=LogLevel.INFO,
            message="Test",
            timestamp="2025-01-01T00:00:00Z",
            logger_name="test",
        )
        
        # Should not raise
        writer.write(entry)
        writer.flush()
        writer.close()
    
    def test_console_writer_text_format(self):
        """Test console writer with TEXT format."""
        writer = ConsoleLogWriter(format=LogFormat.TEXT)
        
        entry = LogEntry(
            entry_id="log_test",
            level=LogLevel.INFO,
            message="Test",
            timestamp="2025-01-01T00:00:00Z",
            logger_name="test",
        )
        
        writer.write(entry)
        writer.flush()
        writer.close()
    
    def test_file_writer(self):
        """Test file writer."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            temp_path = f.name
        
        try:
            writer = FileLogWriter(temp_path, format=LogFormat.JSON)
            
            entry = LogEntry(
                entry_id="log_test",
                level=LogLevel.INFO,
                message="Test message",
                timestamp="2025-01-01T00:00:00Z",
                logger_name="test",
            )
            
            writer.write(entry)
            writer.flush()
            writer.close()
            
            # Verify file content
            with open(temp_path, 'r') as f:
                content = f.read()
            
            assert "log_test" in content
            assert "Test message" in content
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
    
    def test_async_writer(self):
        """Test async writer."""
        output = io.StringIO()
        
        class CaptureWriter:
            def __init__(self, out):
                self.out = out
                self.entries = []
            
            def write(self, entry):
                self.entries.append(entry)
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        base_writer = CaptureWriter(output)
        async_writer = AsyncLogWriter(base_writer, buffer_size=10)
        
        entry = LogEntry(
            entry_id="log_test",
            level=LogLevel.INFO,
            message="Test",
            timestamp="2025-01-01T00:00:00Z",
            logger_name="test",
        )
        
        async_writer.write(entry)
        
        # Give thread time to process
        time.sleep(0.1)
        
        async_writer.close()
        
        assert len(base_writer.entries) == 1
    
    def test_async_writer_buffer_full(self):
        """Test async writer when buffer is full."""
        class SlowWriter:
            def write(self, entry):
                time.sleep(10)  # Very slow
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        base_writer = SlowWriter()
        async_writer = AsyncLogWriter(base_writer, buffer_size=1)
        
        # First write should succeed
        entry1 = LogEntry(
            entry_id="log_1",
            level=LogLevel.INFO,
            message="Test 1",
            timestamp="2025-01-01T00:00:00Z",
            logger_name="test",
        )
        async_writer.write(entry1)
        
        # Second write should be dropped (buffer full)
        entry2 = LogEntry(
            entry_id="log_2",
            level=LogLevel.INFO,
            message="Test 2",
            timestamp="2025-01-01T00:00:00Z",
            logger_name="test",
        )
        async_writer.write(entry2)  # Should not raise
        
        async_writer.close()
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = LoggingEngine()
        
        engine.info("Test 1")
        engine.info("Test 2")
        engine.warning("Warning")
        engine.error("Error")
        
        stats = engine.get_statistics()
        
        assert stats["total_entries"] == 4
        assert stats["by_level"]["INFO"] == 2
        assert stats["by_level"]["WARNING"] == 1
        assert stats["by_level"]["ERROR"] == 1
    
    def test_statistics_filtered_out(self):
        """Test that filtered out entries are tracked."""
        engine = LoggingEngine()
        
        filter = LogFilter(
            filter_id="f1",
            name="Errors Only",
            min_level=LogLevel.ERROR,
        )
        engine.add_filter(filter)
        
        engine.debug("Debug")
        engine.info("Info")
        engine.warning("Warning")
        engine.error("Error")
        
        stats = engine.get_statistics()
        
        assert stats["filtered_out"] == 3
    
    def test_statistics_dropped(self):
        """Test that dropped entries are tracked."""
        engine = LoggingEngine()
        
        # Add a writer that will fail
        class FailingWriter:
            def write(self, entry):
                raise Exception("Write failed")
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        engine.add_writer(FailingWriter())
        
        engine.info("Test")
        
        stats = engine.get_statistics()
        
        assert stats["dropped"] >= 1
    
    def test_get_filters(self):
        """Test getting all filters."""
        engine = LoggingEngine()
        
        f1 = LogFilter(filter_id="f1", name="Filter 1")
        f2 = LogFilter(filter_id="f2", name="Filter 2")
        
        engine.add_filter(f1)
        engine.add_filter(f2)
        
        filters = engine.get_filters()
        
        assert len(filters) == 2
    
    def test_set_min_level(self):
        """Test setting minimum level for all filters."""
        engine = LoggingEngine()
        
        f1 = LogFilter(filter_id="f1", name="F1", min_level=LogLevel.DEBUG)
        f2 = LogFilter(filter_id="f2", name="F2", min_level=LogLevel.DEBUG)
        
        engine.add_filter(f1)
        engine.add_filter(f2)
        
        engine.set_min_level(LogLevel.ERROR)
        
        filters = engine.get_filters()
        
        assert filters[0]["min_level"] == 40
        assert filters[1]["min_level"] == 40
    
    def test_flush_all_writers(self):
        """Test flushing all writers."""
        engine = LoggingEngine()
        
        flushed = []
        
        class TrackFlushWriter:
            def write(self, entry):
                pass
            
            def flush(self):
                flushed.append(True)
            
            def close(self):
                pass
        
        engine.add_writer(TrackFlushWriter())
        engine.add_writer(TrackFlushWriter())
        
        engine.flush()
        
        assert len(flushed) == 2
    
    def test_close_all_writers(self):
        """Test closing all writers."""
        engine = LoggingEngine()
        
        closed = []
        
        class TrackCloseWriter:
            def write(self, entry):
                pass
            
            def flush(self):
                pass
            
            def close(self):
                closed.append(True)
        
        engine.add_writer(TrackCloseWriter())
        engine.add_writer(TrackCloseWriter())
        
        engine.close()
        
        assert len(closed) == 2
    
    def test_log_level_enum_values(self):
        """Test log level enum values."""
        assert LogLevel.DEBUG.value == 10
        assert LogLevel.INFO.value == 20
        assert LogLevel.WARNING.value == 30
        assert LogLevel.ERROR.value == 40
        assert LogLevel.CRITICAL.value == 50
    
    def test_log_format_enum_values(self):
        """Test log format enum values."""
        assert LogFormat.JSON.value == "json"
        assert LogFormat.TEXT.value == "text"
    
    def test_statistics_total_writers(self):
        """Test that statistics include total writers."""
        engine = LoggingEngine()
        
        engine.add_writer(ConsoleLogWriter())
        engine.add_writer(ConsoleLogWriter())
        
        stats = engine.get_statistics()
        
        assert stats["total_writers"] == 2
    
    def test_statistics_total_filters(self):
        """Test that statistics include total filters."""
        engine = LoggingEngine()
        
        engine.add_filter(LogFilter(filter_id="f1", name="F1"))
        engine.add_filter(LogFilter(filter_id="f2", name="F2"))
        
        stats = engine.get_statistics()
        
        assert stats["total_filters"] == 2
    
    def test_statistics_total_buffers(self):
        """Test that statistics include total buffers."""
        engine = LoggingEngine()
        
        engine.create_buffer("b1")
        engine.create_buffer("b2")
        engine.create_buffer("b3")
        
        stats = engine.get_statistics()
        
        assert stats["total_buffers"] == 3
    
    def test_buffer_created_at_tracked(self):
        """Test that buffer created_at is tracked."""
        buffer = LogBuffer()
        
        assert buffer.created_at is not None
    
    def test_multiple_filters_all_must_pass(self):
        """Test that entry must pass all filters."""
        engine = LoggingEngine()
        
        # Filter 1: WARNING and above
        f1 = LogFilter(filter_id="f1", name="F1", min_level=LogLevel.WARNING)
        # Filter 2: Only api loggers
        f2 = LogFilter(filter_id="f2", name="F2", include_loggers=["api"])
        
        engine.add_filter(f1)
        engine.add_filter(f2)
        
        output = io.StringIO()
        
        class CaptureWriter:
            def __init__(self, out):
                self.out = out
                self.entries = []
            
            def write(self, entry):
                self.entries.append(entry)
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        writer = CaptureWriter(output)
        engine.add_writer(writer)
        
        # Should pass both: WARNING + api logger
        engine.warning("API warning", logger_name="api.service")
        
        # Should fail filter 1: level too low
        engine.info("API info", logger_name="api.service")
        
        # Should fail filter 2: wrong logger
        engine.warning("DB warning", logger_name="db.service")
        
        assert len(writer.entries) == 1
    
    def test_entry_id_unique(self):
        """Test that entry IDs are unique."""
        engine = LoggingEngine()
        
        ids = set()
        for i in range(100):
            entry_id = engine.info(f"Message {i}")
            ids.add(entry_id)
        
        assert len(ids) == 100
    
    def test_timestamp_iso_format(self):
        """Test that timestamp is in ISO format."""
        engine = LoggingEngine()
        
        output = io.StringIO()
        
        class CaptureWriter:
            def __init__(self, out):
                self.out = out
                self.last_entry = None
            
            def write(self, entry):
                self.last_entry = entry
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        writer = CaptureWriter(output)
        engine.add_writer(writer)
        
        engine.info("Test")
        
        # Should be parseable ISO format
        assert "T" in writer.last_entry.timestamp
        assert "+" in writer.last_entry.timestamp or "Z" in writer.last_entry.timestamp
    
    def test_extra_data_preserved(self):
        """Test that extra data is preserved."""
        engine = LoggingEngine()
        
        output = io.StringIO()
        
        class CaptureWriter:
            def __init__(self, out):
                self.out = out
                self.last_entry = None
            
            def write(self, entry):
                self.last_entry = entry
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        writer = CaptureWriter(output)
        engine.add_writer(writer)
        
        engine.info(
            "Test",
            extra={"user": "alice", "action": "login", "success": True, "duration_ms": 150},
        )
        
        assert writer.last_entry.extra["user"] == "alice"
        assert writer.last_entry.extra["action"] == "login"
        assert writer.last_entry.extra["success"] is True
        assert writer.last_entry.extra["duration_ms"] == 150
    
    def test_context_copied_per_entry(self):
        """Test that context is copied per entry."""
        engine = LoggingEngine()
        
        output = io.StringIO()
        
        class CaptureWriter:
            def __init__(self, out):
                self.out = out
                self.entries = []
            
            def write(self, entry):
                self.entries.append(entry)
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        writer = CaptureWriter(output)
        engine.add_writer(writer)
        
        engine.set_context("request_id", "req_1")
        engine.info("First message")
        
        engine.set_context("request_id", "req_2")
        engine.info("Second message")
        
        assert writer.entries[0].context["request_id"] == "req_1"
        assert writer.entries[1].context["request_id"] == "req_2"
    
    def test_empty_filters_pass_all(self):
        """Test that no filters means all entries pass."""
        engine = LoggingEngine()
        
        output = io.StringIO()
        
        class CaptureWriter:
            def __init__(self, out):
                self.out = out
                self.entries = []
            
            def write(self, entry):
                self.entries.append(entry)
            
            def flush(self):
                pass
            
            def close(self):
                pass
        
        writer = CaptureWriter(output)
        engine.add_writer(writer)
        
        engine.debug("Debug")
        engine.info("Info")
        
        assert len(writer.entries) == 2
    
    def test_file_writer_text_format(self):
        """Test file writer with text format."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.log') as f:
            temp_path = f.name
        
        try:
            writer = FileLogWriter(temp_path, format=LogFormat.TEXT)
            
            entry = LogEntry(
                entry_id="log_test",
                level=LogLevel.INFO,
                message="Test message",
                timestamp="2025-01-01T00:00:00Z",
                logger_name="test",
            )
            
            writer.write(entry)
            writer.close()
            
            with open(temp_path, 'r') as f:
                content = f.read()
            
            assert "[INFO]" in content
            assert "Test message" in content
        finally:
            if os.path.exists(temp_path):
                os.unlink(temp_path)
