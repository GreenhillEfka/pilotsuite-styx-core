"""Logging Engine — Slice 47.

Structured logging for PilotSuite Core.

Features:
- Structured JSON logging
- Log levels (DEBUG, INFO, WARNING, ERROR, CRITICAL)
- Context propagation
- Log buffering and batching
- Log filtering and sampling
- Async log writing
- Log rotation support
"""
from __future__ import annotations

import json
import logging
import sys
import threading
import queue
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import uuid
from collections import deque

logger = logging.getLogger(__name__)


class LogLevel(Enum):
    """Log levels."""
    DEBUG = 10
    INFO = 20
    WARNING = 30
    ERROR = 40
    CRITICAL = 50


class LogFormat(Enum):
    """Log output formats."""
    JSON = "json"
    TEXT = "text"


@dataclass
class LogEntry:
    """Structured log entry."""
    entry_id: str
    level: LogLevel
    message: str
    timestamp: str
    logger_name: str
    context: Dict[str, Any] = field(default_factory=dict)
    extra: Dict[str, Any] = field(default_factory=dict)
    exception: Optional[str] = None
    source_file: Optional[str] = None
    source_line: Optional[int] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "entry_id": self.entry_id,
            "level": self.level.value,
            "level_name": self.level.name,
            "message": self.message,
            "timestamp": self.timestamp,
            "logger_name": self.logger_name,
            "context": self.context,
            "extra": self.extra,
            "exception": self.exception,
            "source_file": self.source_file,
            "source_line": self.source_line,
        }
    
    def to_json(self) -> str:
        return json.dumps(self.to_dict())


@dataclass
class LogBuffer:
    """Buffer for log entries."""
    entries: deque = field(default_factory=deque)
    max_size: int = 1000
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def add(self, entry: LogEntry) -> bool:
        """Add entry to buffer."""
        if len(self.entries) >= self.max_size:
            self.entries.popleft()  # Drop oldest
        self.entries.append(entry)
        return True
    
    def drain(self) -> List[LogEntry]:
        """Drain all entries from buffer."""
        entries = list(self.entries)
        self.entries.clear()
        return entries
    
    def size(self) -> int:
        return len(self.entries)


@dataclass
class LogFilter:
    """Log filter configuration."""
    filter_id: str
    name: str
    min_level: LogLevel = LogLevel.DEBUG
    include_loggers: List[str] = field(default_factory=list)
    exclude_loggers: List[str] = field(default_factory=list)
    include_patterns: List[str] = field(default_factory=list)
    exclude_patterns: List[str] = field(default_factory=list)
    sample_rate: float = 1.0  # 0.0-1.0
    
    def matches(self, entry: LogEntry) -> bool:
        """Check if entry matches filter."""
        import re
        
        # Check level
        if entry.level.value < self.min_level.value:
            return False
        
        # Check logger includes
        if self.include_loggers:
            if not any(entry.logger_name.startswith(prefix) for prefix in self.include_loggers):
                return False
        
        # Check logger excludes
        if self.exclude_loggers:
            if any(entry.logger_name.startswith(prefix) for prefix in self.exclude_loggers):
                return False
        
        # Check message patterns
        if self.include_patterns:
            if not any(re.search(p, entry.message) for p in self.include_patterns):
                return False
        
        if self.exclude_patterns:
            if any(re.search(p, entry.message) for p in self.exclude_patterns):
                return False
        
        # Sampling
        if self.sample_rate < 1.0:
            import random
            if random.random() > self.sample_rate:
                return False
        
        return True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "filter_id": self.filter_id,
            "name": self.name,
            "min_level": self.min_level.value,
            "include_loggers": self.include_loggers,
            "exclude_loggers": self.exclude_loggers,
            "include_patterns": self.include_patterns,
            "exclude_patterns": self.exclude_patterns,
            "sample_rate": self.sample_rate,
        }


class LogWriter:
    """Log writer interface."""
    
    def write(self, entry: LogEntry) -> None:
        raise NotImplementedError
    
    def flush(self) -> None:
        raise NotImplementedError
    
    def close(self) -> None:
        raise NotImplementedError


class ConsoleLogWriter(LogWriter):
    """Write logs to console."""
    
    def __init__(self, format: LogFormat = LogFormat.TEXT):
        self.format = format
    
    def write(self, entry: LogEntry) -> None:
        if self.format == LogFormat.JSON:
            print(entry.to_json(), file=sys.stderr if entry.level.value >= LogLevel.ERROR.value else sys.stdout)
        else:
            level_name = entry.level.name
            print(f"[{entry.timestamp}] [{level_name}] {entry.message}", 
                  file=sys.stderr if entry.level.value >= LogLevel.ERROR.value else sys.stdout)
    
    def flush(self) -> None:
        sys.stdout.flush()
        sys.stderr.flush()
    
    def close(self) -> None:
        pass


class FileLogWriter(LogWriter):
    """Write logs to file."""
    
    def __init__(self, path: str, format: LogFormat = LogFormat.JSON):
        self.path = path
        self.format = format
        self._file = open(path, "a")
        self._lock = threading.Lock()
    
    def write(self, entry: LogEntry) -> None:
        with self._lock:
            if self.format == LogFormat.JSON:
                self._file.write(entry.to_json() + "\n")
            else:
                level_name = entry.level.name
                self._file.write(f"[{entry.timestamp}] [{level_name}] {entry.message}\n")
    
    def flush(self) -> None:
        with self._lock:
            self._file.flush()
    
    def close(self) -> None:
        with self._lock:
            self._file.close()


class AsyncLogWriter(LogWriter):
    """Async log writer with background thread."""
    
    def __init__(self, writer: LogWriter, buffer_size: int = 100):
        self._writer = writer
        self._queue: queue.Queue = queue.Queue(maxsize=buffer_size)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._process, daemon=True)
        self._thread.start()
    
    def _process(self) -> None:
        while not self._stop.is_set():
            try:
                entry = self._queue.get(timeout=1.0)
                self._writer.write(entry)
            except queue.Empty:
                continue
            except Exception as e:
                logger.exception("Async log write failed: %s", e)
    
    def write(self, entry: LogEntry) -> None:
        try:
            self._queue.put_nowait(entry)
        except queue.Full:
            # Drop log if buffer full
            pass
    
    def flush(self) -> None:
        self._writer.flush()
    
    def close(self) -> None:
        self._stop.set()
        self._thread.join(timeout=5.0)
        self._writer.close()


class LoggingEngine:
    """Centralized logging engine."""
    
    def __init__(self, default_level: LogLevel = LogLevel.INFO,
                 default_format: LogFormat = LogFormat.JSON):
        self._default_level = default_level
        self._default_format = default_format
        self._writers: List[LogWriter] = []
        self._filters: Dict[str, LogFilter] = {}
        self._buffers: Dict[str, LogBuffer] = {}
        self._context: Dict[str, Any] = {}
        self._lock = threading.Lock()
        
        # Statistics
        self._stats = {
            "total_entries": 0,
            "by_level": {},
            "by_logger": {},
            "filtered_out": 0,
            "dropped": 0,
        }
    
    def add_writer(self, writer: LogWriter) -> None:
        """Add a log writer."""
        self._writers.append(writer)
        logger.info("Log writer added: %s", type(writer).__name__)
    
    def remove_writer(self, writer: LogWriter) -> bool:
        """Remove a log writer."""
        if writer in self._writers:
            self._writers.remove(writer)
            writer.close()
            return True
        return False
    
    def add_filter(self, filter: LogFilter) -> str:
        """Add a log filter."""
        self._filters[filter.filter_id] = filter
        return filter.filter_id
    
    def remove_filter(self, filter_id: str) -> bool:
        """Remove a log filter."""
        if filter_id in self._filters:
            del self._filters[filter_id]
            return True
        return False
    
    def create_buffer(self, name: str, max_size: int = 1000) -> str:
        """Create a log buffer."""
        buffer_id = f"buf_{uuid.uuid4().hex[:8]}"
        self._buffers[buffer_id] = LogBuffer(max_size=max_size)
        return buffer_id
    
    def get_buffer(self, buffer_id: str) -> Optional[LogBuffer]:
        """Get a log buffer."""
        return self._buffers.get(buffer_id)
    
    def drain_buffer(self, buffer_id: str) -> List[LogEntry]:
        """Drain entries from a buffer."""
        if buffer_id in self._buffers:
            return self._buffers[buffer_id].drain()
        return []
    
    def set_context(self, key: str, value: Any) -> None:
        """Set global context value."""
        with self._lock:
            self._context[key] = value
    
    def clear_context(self, key: Optional[str] = None) -> None:
        """Clear context."""
        with self._lock:
            if key:
                self._context.pop(key, None)
            else:
                self._context.clear()
    
    def get_context(self) -> Dict[str, Any]:
        """Get current context."""
        with self._lock:
            return dict(self._context)
    
    def log(self, level: LogLevel, message: str,
            logger_name: str = "main",
            extra: Optional[Dict[str, Any]] = None,
            exception: Optional[Exception] = None,
            source_file: Optional[str] = None,
            source_line: Optional[int] = None,
            buffer_id: Optional[str] = None) -> Optional[str]:
        """Log a message."""
        entry_id = f"log_{uuid.uuid4().hex[:12]}"
        
        entry = LogEntry(
            entry_id=entry_id,
            level=level,
            message=message,
            timestamp=datetime.now(timezone.utc).isoformat(),
            logger_name=logger_name,
            context=self.get_context(),
            extra=extra or {},
            exception=str(exception) if exception else None,
            source_file=source_file,
            source_line=source_line,
        )
        
        # Update stats
        self._stats["total_entries"] += 1
        level_name = level.name
        self._stats["by_level"][level_name] = self._stats["by_level"].get(level_name, 0) + 1
        self._stats["by_logger"][logger_name] = self._stats["by_logger"].get(logger_name, 0) + 1
        
        # Check filters
        if not self._passes_filters(entry):
            self._stats["filtered_out"] += 1
            return entry_id
        
        # Write to all writers
        for writer in self._writers:
            try:
                writer.write(entry)
            except Exception as e:
                logger.exception("Write failed: %s", e)
                self._stats["dropped"] += 1
        
        # Also add to buffer if specified
        if buffer_id and buffer_id in self._buffers:
            self._buffers[buffer_id].add(entry)
        
        return entry_id
    
    def debug(self, message: str, **kwargs) -> Optional[str]:
        """Log DEBUG message."""
        return self.log(LogLevel.DEBUG, message, **kwargs)
    
    def info(self, message: str, **kwargs) -> Optional[str]:
        """Log INFO message."""
        return self.log(LogLevel.INFO, message, **kwargs)
    
    def warning(self, message: str, **kwargs) -> Optional[str]:
        """Log WARNING message."""
        return self.log(LogLevel.WARNING, message, **kwargs)
    
    def error(self, message: str, **kwargs) -> Optional[str]:
        """Log ERROR message."""
        return self.log(LogLevel.ERROR, message, **kwargs)
    
    def critical(self, message: str, **kwargs) -> Optional[str]:
        """Log CRITICAL message."""
        return self.log(LogLevel.CRITICAL, message, **kwargs)
    
    def exception(self, message: str, exc: Exception, **kwargs) -> Optional[str]:
        """Log exception."""
        return self.log(LogLevel.ERROR, message, exception=exc, **kwargs)
    
    def _passes_filters(self, entry: LogEntry) -> bool:
        """Check if entry passes all filters."""
        if not self._filters:
            return True
        
        for filter in self._filters.values():
            if not filter.matches(entry):
                return False
        
        return True
    
    def flush(self) -> None:
        """Flush all writers."""
        for writer in self._writers:
            try:
                writer.flush()
            except Exception as e:
                logger.exception("Flush failed: %s", e)
    
    def close(self) -> None:
        """Close all writers."""
        for writer in self._writers:
            try:
                writer.close()
            except Exception as e:
                logger.exception("Close failed: %s", e)
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get logging statistics."""
        return {
            **self._stats,
            "total_writers": len(self._writers),
            "total_filters": len(self._filters),
            "total_buffers": len(self._buffers),
        }
    
    def get_filters(self) -> List[Dict[str, Any]]:
        """Get all filters."""
        return [f.to_dict() for f in self._filters.values()]
    
    def set_min_level(self, level: LogLevel) -> None:
        """Set minimum log level for all filters."""
        for filter in self._filters.values():
            filter.min_level = level


def create_logging_engine(level: LogLevel = LogLevel.INFO,
                         format: LogFormat = LogFormat.JSON) -> LoggingEngine:
    """Factory function to create logging engine."""
    return LoggingEngine(default_level=level, default_format=format)
