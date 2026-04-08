"""
Error Status API - Error Dashboard Widget für Styx Dashboard

Endpoints:
- GET /api/v1/errors/status → Gesamter Status
- GET /api/v1/errors/history → Letzte 10 Fehler
- GET /api/v1/errors/modules → Fehler pro Modul
"""

import logging
import time
from datetime import datetime
from typing import List, Dict, Any, Optional
from collections import deque
from dataclasses import dataclass, field, asdict

_LOGGER = logging.getLogger(__name__)


@dataclass
class ErrorEntry:
    """Single error entry for history."""
    module: str
    function: str
    message: str
    timestamp: float
    traceback: str = ""
    
    def to_dict(self) -> dict:
        return {
            "module": self.module,
            "function": self.function,
            "message": self.message,
            "timestamp": self.timestamp,
            "datetime": datetime.fromtimestamp(self.timestamp).isoformat(),
            "traceback": self.traceback[:500] if self.traceback else "",
        }


class ErrorHistory:
    """Thread-safe error history with limited size."""
    
    def __init__(self, max_entries: int = 100, max_per_module: int = 10):
        self.max_entries = max_entries
        self.max_per_module = max_per_module
        
        self._history: deque = deque(maxlen=max_entries)
        self._module_errors: Dict[str, deque] = {}
        self._lock = __import__("threading").RLock()
    
    def add(self, module: str, function: str, message: str, traceback_str: str = "") -> None:
        """Add an error entry."""
        entry = ErrorEntry(
            module=module,
            function=function,
            message=message,
            timestamp=time.time(),
            traceback=traceback_str,
        )
        
        with self._lock:
            self._history.append(entry)
            
            # Track per-module errors
            if module not in self._module_errors:
                self._module_errors[module] = deque(maxlen=self.max_per_module)
            self._module_errors[module].append(entry)
    
    def get_all(self, limit: int = 10) -> List[Dict]:
        """Get last N errors."""
        with self._lock:
            return [e.to_dict() for e in list(self._history)[-limit:]]
    
    def get_by_module(self, module: str, limit: int = 10) -> List[Dict]:
        """Get last N errors for a specific module."""
        with self._lock:
            if module in self._module_errors:
                return [e.to_dict() for e in list(self._module_errors[module])[-limit:]]
            return []
    
    def get_counts(self) -> Dict[str, int]:
        """Get error count per module."""
        with self._lock:
            return {m: len(e) for m, e in self._module_errors.items()}
    
    def get_summary(self) -> Dict[str, Any]:
        """Get error summary."""
        with self._lock:
            return {
                "total_errors": len(self._history),
                "modules_with_errors": len(self._module_errors),
                "error_counts": self.get_counts(),
                "last_10": self.get_all(10),
            }


# Global error history instance
error_history = ErrorHistory(max_entries=100, max_per_module=10)


def register_error(module: str, function: str, message: str, traceback_str: str = "") -> None:
    """Register an error for the dashboard."""
    error_history.add(module, function, message, traceback_str)
    _LOGGER.warning(f"[{module}] Error in {function}: {message}")


def get_error_status() -> Dict[str, Any]:
    """Get current error status for the dashboard."""
    return error_history.get_summary()


def get_error_history(limit: int = 10) -> List[Dict]:
    """Get error history."""
    return error_history.get_all(limit)


def get_module_errors(module: str) -> List[Dict]:
    """Get errors for a specific module."""
    return error_history.get_by_module(module, limit=10)
