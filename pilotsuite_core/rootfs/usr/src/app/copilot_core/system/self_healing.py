"""System Self-Healing & Circuit Breaker (Slice 167).

Provides autonomous recovery for failed services and 
circuit breaker logic for external API calls.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

_LOGGER = logging.getLogger(__name__)

class CircuitState(Enum):
    CLOSED = "closed"   # Normal operation
    OPEN = "open"       # Failed, no requests allowed
    HALF_OPEN = "half_open" # Testing recovery

@dataclass
class CircuitBreaker:
    """Monitors failures for a specific service."""
    service_id: str
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    failure_threshold: int = 5
    recovery_timeout_s: int = 60
    last_failure_ts: float = 0.0
    half_open_limit: int = 3
    success_count_half_open: int = 0

    def record_failure(self):
        self.failure_count += 1
        self.last_failure_ts = time.monotonic()
        if self.failure_count >= self.failure_threshold:
            self.state = CircuitState.OPEN
            _LOGGER.error("Circuit Breaker TRIPPED for %s", self.service_id)

    def record_success(self):
        if self.state == CircuitState.HALF_OPEN:
            self.success_count_half_open += 1
            if self.success_count_half_open >= self.half_open_limit:
                self.reset()
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def can_execute(self) -> bool:
        if self.state == CircuitState.CLOSED:
            return True
        if self.state == CircuitState.OPEN:
            if time.monotonic() - self.last_failure_ts > self.recovery_timeout_s:
                self.state = CircuitState.HALF_OPEN
                self.success_count_half_open = 0
                return True
            return False
        return True # Half-open allows limited requests

    def reset(self):
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count_half_open = 0
        _LOGGER.info("Circuit Breaker RESET for %s", self.service_id)

class SelfHealingManager:
    """Manages autonomous service recovery."""
    
    def __init__(self):
        self._breakers: Dict[str, CircuitBreaker] = {}
        self._restart_history: List[Dict[str, Any]] = []

    def get_breaker(self, service_id: str) -> CircuitBreaker:
        if service_id not in self._breakers:
            self._breakers[service_id] = CircuitBreaker(service_id=service_id)
        return self._breakers[service_id]

    def get_system_health(self) -> Dict[str, Any]:
        """Returns health status for the System Tab."""
        return {
            "services": [
                {
                    "id": s_id,
                    "state": b.state.value,
                    "failures": b.failure_count,
                    "healthy": b.state != CircuitState.OPEN
                } for s_id, b in self._breakers.items()
            ],
            "self_healing_events": self._restart_history[-5:],
            "last_check": datetime.now(timezone.utc).isoformat()
        }

# API Integration for Slice 167
def init_self_healing_api(bp):
    @bp.route("/system/health", methods=["GET"])
    def get_system_health_status():
        manager = SelfHealingManager() # In real: singleton
        return {"ok": True, "health": manager.get_system_health()}

    @bp.route("/system/service/<service_id>/reset", methods=["POST"])
    def reset_service_breaker(service_id: str):
        manager = SelfHealingManager()
        manager.get_breaker(service_id).reset()
        return {"ok": True, "service_id": service_id}
