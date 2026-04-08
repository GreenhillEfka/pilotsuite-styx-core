"""Dev Surface service for observability and debugging."""
import os
import json
import threading
import traceback
import psutil
from collections import deque, Counter
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Optional, Any

from .models import DevLogEntry, ErrorSummary, SystemHealth


class DevSurfaceService:
    """Central service for developer observability features."""
    
    def __init__(self, max_log_entries: int = 500, log_file_path: Optional[str] = None):
        self.max_log_entries = max_log_entries
        configured_path = (
            log_file_path
            or os.environ.get("COPILOT_DEV_LOG_FILE")
            or "/data/dev_logs.jsonl"
        )
        self.log_file_path = self._resolve_log_file_path(configured_path)
        self._lock = threading.Lock()
        
        # Ring buffer for in-memory log entries
        self._log_entries: deque[DevLogEntry] = deque(maxlen=max_log_entries)
        
        # Error tracking
        self._error_counts = Counter()
        self._last_error: Optional[DevLogEntry] = None
        
        # Stats
        self._events_processed_24h = 0
        self._errors_24h = 0
        
    def _resolve_log_file_path(self, configured_path: str) -> str:
        """Pick a writable log file path, falling back outside add-on runtime."""
        log_dir = os.path.dirname(configured_path) or "."
        try:
            os.makedirs(log_dir, exist_ok=True)
            return configured_path
        except OSError:
            fallback_dir = os.environ.get("COPILOT_DEV_LOG_DIR", "/tmp")
            fallback_path = os.path.join(fallback_dir, "dev_logs.jsonl")
            os.makedirs(os.path.dirname(fallback_path), exist_ok=True)
            return fallback_path
    
    def log(self, level: str, module: str, message: str, **kwargs) -> DevLogEntry:
        """Add a structured log entry."""
        entry = DevLogEntry.create(level, module, message, **kwargs)
        
        with self._lock:
            self._log_entries.append(entry)
            
            # Track errors
            if level.upper() in ['ERROR', 'WARN']:
                self._errors_24h += 1
                if level.upper() == 'ERROR':
                    self._last_error = entry
                    error_key = kwargs.get('error_type', 'unknown_error')
                    self._error_counts[error_key] += 1
            
            # Persist to file (non-blocking, best effort)
            try:
                with open(self.log_file_path, "a", encoding="utf-8") as f:
                    f.write(json.dumps(entry.to_dict()) + "\n")
            except Exception:
                # Don't let logging failures break the main flow
                pass
        
        return entry
    
    def debug(self, module: str, message: str, **kwargs):
        """Log debug message."""
        return self.log("DEBUG", module, message, **kwargs)
    
    def info(self, module: str, message: str, **kwargs):
        """Log info message."""
        return self.log("INFO", module, message, **kwargs)
    
    def warn(self, module: str, message: str, **kwargs):
        """Log warning message."""
        return self.log("WARN", module, message, **kwargs)
    
    def error(self, module: str, message: str, error: Optional[Exception] = None, **kwargs):
        """Log error message with optional exception details."""
        if error:
            kwargs['error_type'] = type(error).__name__
            kwargs['stack_trace'] = traceback.format_exc()
        return self.log("ERROR", module, message, **kwargs)
    
    def get_recent_logs(self, limit: Optional[int] = None, level_filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get recent log entries, optionally filtered by level."""
        with self._lock:
            entries = list(self._log_entries)
        
        if level_filter:
            level_filter = level_filter.upper()
            entries = [e for e in entries if e.level == level_filter]
        
        if limit:
            entries = entries[-limit:]
        
        return [entry.to_dict() for entry in entries]
    
    def get_error_summary(self) -> ErrorSummary:
        """Get summary of recent errors."""
        with self._lock:
            most_frequent = self._error_counts.most_common(1)
            most_frequent_error = most_frequent[0][0] if most_frequent else None
            
            return ErrorSummary(
                last_error=self._last_error,
                error_counts=dict(self._error_counts),
                total_errors_24h=self._errors_24h,
                most_frequent_error=most_frequent_error
            )
    
    def get_system_health(self, brain_graph_service=None) -> SystemHealth:
        """Get current system health snapshot."""
        try:
            # Get memory usage
            process = psutil.Process()
            memory_mb = process.memory_info().rss / 1024 / 1024
        except Exception:
            memory_mb = None
        
        # Get brain graph stats if service available
        brain_nodes = 0
        brain_edges = 0
        if brain_graph_service:
            try:
                stats = brain_graph_service.get_stats()
                brain_nodes = stats.get("total_nodes", 0)
                brain_edges = stats.get("total_edges", 0)
            except Exception:
                pass
        
        # Determine health status
        status = "healthy"
        if self._errors_24h > 10:
            status = "degraded"
        if self._errors_24h > 50:
            status = "error"
        
        return SystemHealth.create_current(
            memory_usage_mb=memory_mb,
            brain_graph_nodes=brain_nodes,
            brain_graph_edges=brain_edges,
            events_processed_24h=self._events_processed_24h,
            errors_24h=self._errors_24h,
            status=status,
            cache_enabled=True,  # Always enabled now
            cache_hits=getattr(self, '_cache_hits', 0),
            cache_misses=getattr(self, '_cache_misses', 0),
            cache_evictions=getattr(self, '_cache_evictions', 0),
            batch_mode_enabled=getattr(self, '_batch_mode_enabled', False),
            pending_invalidations=getattr(self, '_pending_invalidations', 0)
        )
    
    def clear_logs(self):
        """Clear all in-memory log entries."""
        with self._lock:
            self._log_entries.clear()
            self._error_counts.clear()
            self._last_error = None
            self._errors_24h = 0
            self._events_processed_24h = 0
    
    def increment_events_processed(self, count: int = 1):
        """Track processed events for metrics."""
        with self._lock:
            self._events_processed_24h += count
    
    def export_diagnostics(self) -> Dict[str, Any]:
        """Export comprehensive diagnostics data."""
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "system_health": self.get_system_health().to_dict(),
            "error_summary": self.get_error_summary().to_dict(),
            "recent_logs": self.get_recent_logs(limit=50),
            "version": os.environ.get("COPILOT_VERSION", "unknown")
        }


# Global instance for easy access
dev_surface = DevSurfaceService()
