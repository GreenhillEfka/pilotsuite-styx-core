"""
Error Boundary - Module-Crash-Isolation für PilotSuite Core

Jedes Modul kann seinen Code in einem ErrorBoundary ausführen,
um sicherzustellen, dass crashes nicht auf andere Module übertragen werden.

This module provides:
- ModuleErrorBoundary: Decorator-based error isolation
- safe_execute: Helper for wrapping arbitrary functions
- HAConnectionPool: HA client session pooling with cleanup
"""

import logging
import traceback
from functools import wraps
from typing import Callable, Any, Optional, TypeVar, ParamSpec

from copilot_core.performance import sql_pool

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")
P = ParamSpec("P")


class ModuleErrorBoundary:
    """
    Wraps module functions to isolate crashes.
    
    Usage:
        @ModuleErrorBoundary.wrap
        def my_module_function():
            ...
    """
    
    def __init__(self, module_name: str, fail_fast: bool = False):
        """
        Initialize the error boundary.
        
        Args:
            module_name: Name of the module for logging
            fail_fast: If True, re-raises the exception (for critical modules)
        """
        self.module_name = module_name
        self.fail_fast = fail_fast
        self.error_count = 0
        self.last_error: Optional[Exception] = None
    
    def wrap(self, func: Callable[P, T]) -> Callable[P, Optional[T]]:
        """Decorator to wrap a function with error isolation."""
        @wraps(func)
        def wrapper(*args: P.args, **kwargs: P.kwargs) -> Optional[T]:
            try:
                return func(*args, **kwargs)
            except Exception as e:
                self.error_count += 1
                self.last_error = e
                _LOGGER.error(
                    f"[{self.module_name}] Error in {func.__name__}: {e}\n"
                    f"Traceback: {traceback.format_exc()}"
                )
                if self.fail_fast:
                    raise
                return None
        
        return wrapper
    
    def execute(self, func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> Optional[T]:
        """Execute a function with error isolation."""
        try:
            return func(*args, **kwargs)
        except Exception as e:
            self.error_count += 1
            self.last_error = e
            _LOGGER.error(
                f"[{self.module_name}] Error in execution: {e}\n"
                f"Traceback: {traceback.format_exc()}"
            )
            if self.fail_fast:
                raise
            return None
    
    def reset(self):
        """Reset error counters."""
        self.error_count = 0
        self.last_error = None


def safe_execute(module_name: str, func: Callable[P, T], *args: P.args, **kwargs: P.kwargs) -> Optional[T]:
    """
    Execute a function with error isolation.
    
    Usage:
        result = safe_execute("my_module", my_function, arg1, arg2)
    """
    boundary = ModuleErrorBoundary(module_name)
    return boundary.execute(func, *args, **kwargs)


# Connection pool with HA session management
# This wraps the existing sql_pool with HA-client-specific pooling
class HAConnectionPool:
    """Connection pool for HA client sessions with automatic cleanup."""
    
    def __init__(self, pool: Any = None):
        self._pool = pool or sql_pool
        self._ha_sessions: dict = {}
        self._lock = __import__("threading").RLock()
    
    def setup_ha_session(self, session_id: str, client_session: Any) -> None:
        """Register a HA client session."""
        with self._lock:
            self._ha_sessions[session_id] = {
                "session": client_session,
                "created_at": __import__("time").time(),
            }
    
    def cleanup_ha_session(self, session_id: str) -> bool:
        """Clean up a HA client session."""
        with self._lock:
            if session_id in self._ha_sessions:
                session_data = self._ha_sessions.pop(session_id)
                # Close the client session
                session = session_data.get("session")
                if session and hasattr(session, "close"):
                    try:
                        import asyncio
                        if asyncio.get_event_loop().is_running():
                            asyncio.create_task(session.close())
                        else:
                            asyncio.run(session.close())
                    except Exception:
                        pass
                return True
        return False
    
    def cleanup_all_ha_sessions(self) -> int:
        """Clean up all HA client sessions. Returns count cleaned."""
        with self._lock:
            count = len(self._ha_sessions)
            for session_id in list(self._ha_sessions.keys()):
                self.cleanup_ha_session(session_id)
            return count
    
    def get_stats(self) -> dict:
        """Get pool statistics."""
        with self._lock:
            return {
                "active_ha_sessions": len(self._ha_sessions),
                "pool_stats": self._pool.get_stats() if self._pool else {},
            }


# Global HA connection pool
ha_conn_pool = HAConnectionPool()

__all__ = [
    "ModuleErrorBoundary",
    "safe_execute",
    "HAConnectionPool",
    "ha_conn_pool",
]
