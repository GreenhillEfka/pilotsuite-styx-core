"""Circuit Breaker for external service calls (v3.6.0).

Prevents cascading failures when HA Supervisor or Ollama are unreachable.
States: CLOSED (normal) -> OPEN (failing) -> HALF_OPEN (testing recovery).
"""

import logging
import threading
import time
from enum import Enum
from typing import Any, Callable, Optional

_LOGGER = logging.getLogger(__name__)


class CircuitState(Enum):
    CLOSED = "closed"       # Normal operation
    OPEN = "open"           # Failing — reject calls fast
    HALF_OPEN = "half_open" # Testing if service recovered


class CircuitBreaker:
    """Per-service circuit breaker.

    Usage::

        cb = CircuitBreaker("ha_supervisor", failure_threshold=5, recovery_timeout=30)
        try:
            result = cb.call(lambda: requests.get(url, timeout=5))
        except CircuitOpenError:
            # Service is down, use cached/fallback data
            ...
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
    ):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout

        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._last_failure_time: float = 0
        self._lock = threading.Lock()

    @property
    def state(self) -> CircuitState:
        with self._lock:
            if self._state == CircuitState.OPEN:
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = CircuitState.HALF_OPEN
            return self._state

    def call(self, func: Callable[[], Any]) -> Any:
        """Execute *func* through the circuit breaker.

        Raises :class:`CircuitOpenError` if the circuit is open.
        """
        current = self.state

        if current == CircuitState.OPEN:
            raise CircuitOpenError(
                f"Circuit '{self.name}' is OPEN — service unavailable "
                f"(failures={self._failure_count}, retry in "
                f"{self.recovery_timeout - (time.time() - self._last_failure_time):.0f}s)"
            )

        try:
            result = func()
            self._on_success()
            return result
        except Exception as exc:
            self._on_failure()
            raise exc

    def _on_success(self) -> None:
        with self._lock:
            self._failure_count = 0
            if self._state == CircuitState.HALF_OPEN:
                _LOGGER.info("Circuit '%s' recovered -> CLOSED", self.name)
            self._state = CircuitState.CLOSED

    def _on_failure(self) -> None:
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self.failure_threshold:
                if self._state != CircuitState.OPEN:
                    _LOGGER.warning(
                        "Circuit '%s' -> OPEN (failures=%d)",
                        self.name, self._failure_count,
                    )
                self._state = CircuitState.OPEN

    def get_status(self) -> dict:
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self._failure_count,
            "failure_threshold": self.failure_threshold,
            "recovery_timeout_s": self.recovery_timeout,
        }


class CircuitOpenError(Exception):
    """Raised when the circuit breaker is open."""
    pass


# ---------------------------------------------------------------------------
# Global circuit breakers for external services
# ---------------------------------------------------------------------------

ha_supervisor_breaker = CircuitBreaker(
    "ha_supervisor", failure_threshold=5, recovery_timeout=30
)

ollama_breaker = CircuitBreaker(
    "ollama", failure_threshold=3, recovery_timeout=60
)


def get_all_breaker_status() -> list[dict]:
    """Return status of all global circuit breakers."""
    return [
        ha_supervisor_breaker.get_status(),
        ollama_breaker.get_status(),
    ]
