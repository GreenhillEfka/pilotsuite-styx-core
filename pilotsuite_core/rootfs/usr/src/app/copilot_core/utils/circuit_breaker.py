"""Circuit Breaker Pattern - Core Stability (Slice 143).

Prevents cascading failures when external services are down.
States: CLOSED (normal), OPEN (failing), HALF_OPEN (testing).
"""

from __future__ import annotations

import logging
import threading
import time
from enum import Enum
from functools import wraps
from typing import Any, Callable, Optional, TypeVar

_LOGGER = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject fast
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker for external service calls.
    
    Slice 143: Prevents Backend-UI hanging when services are down.
    """
    
    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        half_open_max_calls: int = 3,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.half_open_max_calls = half_open_max_calls
        
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time: Optional[float] = None
        self._half_open_calls = 0
        self._lock = threading.Lock()
    
    @property
    def state(self) -> CircuitState:
        """Current circuit state."""
        with self._lock:
            return self._state
    
    def can_execute(self) -> bool:
        """Check if execution is allowed."""
        with self._lock:
            if self._state == CircuitState.CLOSED:
                return True
            
            if self._state == CircuitState.OPEN:
                if time.monotonic() - (self._last_failure_time or 0) > self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
                    self._half_open_calls = 0
                    _LOGGER.info(f"Circuit {self.name}: OPEN -> HALF_OPEN (testing recovery)")
                    return True
                return False
            
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls < self.half_open_max_calls:
                    self._half_open_calls += 1
                    return True
                return False
            
            return True
    
    def record_success(self) -> None:
        """Record successful execution."""
        with self._lock:
            self._failure_count = 0
            
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                if self._success_count >= self.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._half_open_calls = 0
                    self._success_count = 0
                    _LOGGER.info(f"Circuit {self.name}: HALF_OPEN -> CLOSED (recovered)")
    
    def record_failure(self) -> None:
        """Record failed execution."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            
            if self._state == CircuitState.CLOSED:
                if self._failure_count >= self.failure_threshold:
                    self._state = CircuitState.OPEN
                    _LOGGER.warning(
                        f"Circuit {self.name}: CLOSED -> OPEN ({self._failure_count} failures)"
                    )
            
            elif self._state == CircuitState.HALF_OPEN:
                self._state = CircuitState.OPEN
                self._half_open_calls = 0
                _LOGGER.warning(f"Circuit {self.name}: HALF_OPEN -> OPEN (still failing)")


# Global circuit breakers registry
_circuit_breakers: dict[str, CircuitBreaker] = {}
_circuit_lock = threading.Lock()


def get_circuit_breaker(name: str) -> CircuitBreaker:
    """Get or create circuit breaker by name."""
    with _circuit_lock:
        if name not in _circuit_breakers:
            _circuit_breakers[name] = CircuitBreaker(name)
        return _circuit_breakers[name]


def circuit_breaker(
    name: str,
    fallback: Optional[Callable[..., T]] = None,
):
    """Decorator to wrap function with circuit breaker.
    
    Args:
        name: Circuit breaker name
        fallback: Optional fallback function if circuit is open
    """
    def decorator(func: Callable[..., T]) -> Callable[..., Optional[T]]:
        breaker = get_circuit_breaker(name)
        
        @wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Optional[T]:
            if not breaker.can_execute():
                _LOGGER.debug(f"Circuit {name}: Rejecting call (state={breaker.state.value})")
                if fallback:
                    return fallback(*args, **kwargs)
                return None
            
            try:
                result = func(*args, **kwargs)
                breaker.record_success()
                return result
            except Exception as exc:
                breaker.record_failure()
                _LOGGER.warning(f"Circuit {name}: Execution failed: {exc}")
                if fallback:
                    return fallback(*args, **kwargs)
                raise
        
        return wrapper
    return decorator
