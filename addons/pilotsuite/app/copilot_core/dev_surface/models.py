"""Data models for dev surface observability."""
import time
from dataclasses import dataclass, asdict
from typing import Optional, Dict, List, Any
from datetime import datetime, timezone


@dataclass
class DevLogEntry:
    """Structured log entry for developer debugging."""
    
    timestamp: str
    level: str  # DEBUG, INFO, WARN, ERROR
    module: str
    message: str
    context: Optional[Dict[str, Any]] = None
    error_type: Optional[str] = None
    stack_trace: Optional[str] = None
    duration_ms: Optional[float] = None  # Operation duration for perf tracking
    
    @classmethod
    def create(cls, level: str, module: str, message: str, **kwargs) -> 'DevLogEntry':
        """Create a new dev log entry with current timestamp."""
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(),
            level=level.upper(),
            module=module,
            message=message,
            **kwargs
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


@dataclass 
class ErrorSummary:
    """Summary of recent errors for quick diagnosis."""
    
    last_error: Optional[DevLogEntry] = None
    error_counts: Dict[str, int] = None
    total_errors_24h: int = 0
    most_frequent_error: Optional[str] = None
    
    def __post_init__(self):
        if self.error_counts is None:
            self.error_counts = {}
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        result = {
            "total_errors_24h": self.total_errors_24h,
            "error_counts": self.error_counts,
            "most_frequent_error": self.most_frequent_error,
            "last_error": self.last_error.to_dict() if self.last_error else None
        }
        return result


@dataclass
class SystemHealth:
    """Overall system health snapshot."""
    
    timestamp: str
    uptime_seconds: float
    memory_usage_mb: Optional[float] = None
    brain_graph_nodes: int = 0
    brain_graph_edges: int = 0
    events_processed_24h: int = 0
    errors_24h: int = 0
    status: str = "unknown"  # healthy, degraded, error
    cache_enabled: bool = False
    cache_hits: int = 0
    cache_misses: int = 0
    cache_evictions: int = 0
    batch_mode_enabled: bool = False
    pending_invalidations: int = 0
    
    @classmethod
    def create_current(cls, **kwargs) -> 'SystemHealth':
        """Create system health with current timestamp."""
        return cls(
            timestamp=datetime.now(timezone.utc).isoformat(),
            uptime_seconds=time.time() - _start_time,
            **kwargs
        )
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return asdict(self)


# Global start time for uptime calculation
_start_time = time.time()