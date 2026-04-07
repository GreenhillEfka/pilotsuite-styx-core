"""P1-006: Health Check System — Liveness, Readiness, Startup Probes."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Tuple
from enum import Enum
import asyncio

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class ProbeType(Enum):
    """Probe types for health checks."""
    LIVENESS = "liveness"  # Is the app running?
    READINESS = "readiness"  # Is the app ready to serve traffic?
    STARTUP = "startup"  # Has the app started successfully?


@dataclass
class ProbeResult:
    """Result of a health probe."""
    probe_type: ProbeType
    probe_name: str
    status: HealthStatus
    message: str
    timestamp: float = field(default_factory=time.time)
    duration_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ProbeConfig:
    """Configuration for a health probe."""
    name: str
    probe_type: ProbeType
    check_fn: Callable
    timeout_seconds: float = 5.0
    interval_seconds: float = 10.0
    failure_threshold: int = 3
    success_threshold: int = 1
    initial_delay_seconds: float = 0.0


class DependencyCheck:
    """Checks health of external dependencies."""

    def __init__(self):
        self._checks: Dict[str, Callable] = {}
        self._results: Dict[str, ProbeResult] = {}

    def register_check(self, name: str, check_fn: Callable):
        """Register dependency health check."""
        self._checks[name] = check_fn
        logger.info(f"Registered dependency check: {name}")

    async def check_all(self) -> Dict[str, ProbeResult]:
        """Check all dependencies."""
        results = {}
        for name, check_fn in self._checks.items():
            try:
                start = time.time()
                if asyncio.iscoroutinefunction(check_fn):
                    healthy, message = await check_fn()
                else:
                    healthy, message = check_fn()
                duration_ms = (time.time() - start) * 1000

                results[name] = ProbeResult(
                    probe_type=ProbeType.READINESS,
                    probe_name=name,
                    status=HealthStatus.HEALTHY if healthy else HealthStatus.UNHEALTHY,
                    message=message,
                    duration_ms=duration_ms
                )
            except Exception as e:
                results[name] = ProbeResult(
                    probe_type=ProbeType.READINESS,
                    probe_name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=str(e),
                    duration_ms=0.0
                )
        
        self._results = results
        return results

    def get_results(self) -> Dict[str, ProbeResult]:
        """Get latest dependency check results."""
        return self._results


class HealthProbe:
    """Single health probe with state tracking."""

    def __init__(self, config: ProbeConfig):
        self.config = config
        self.consecutive_failures = 0
        self.consecutive_successes = 0
        self.last_check: Optional[float] = None
        self.last_result: Optional[ProbeResult] = None
        self._enabled = True

    async def run(self) -> ProbeResult:
        """Run the health probe."""
        if not self._enabled:
            return ProbeResult(
                probe_type=self.config.probe_type,
                probe_name=self.config.name,
                status=HealthStatus.UNKNOWN,
                message="Probe disabled"
            )

        start = time.time()
        self.last_check = time.time()

        try:
            # Run check with timeout
            if asyncio.iscoroutinefunction(self.config.check_fn):
                result = await asyncio.wait_for(
                    self.config.check_fn(),
                    timeout=self.config.timeout_seconds
                )
            else:
                result = self.config.check_fn()

            duration_ms = (time.time() - start) * 1000
            healthy, message = result

            if healthy:
                self.consecutive_successes += 1
                self.consecutive_failures = 0
                status = HealthStatus.HEALTHY
            else:
                self.consecutive_failures += 1
                self.consecutive_successes = 0
                status = HealthStatus.UNHEALTHY

            self.last_result = ProbeResult(
                probe_type=self.config.probe_type,
                probe_name=self.config.name,
                status=status,
                message=message,
                duration_ms=duration_ms
            )
            return self.last_result

        except asyncio.TimeoutError:
            self.consecutive_failures += 1
            self.last_result = ProbeResult(
                probe_type=self.config.probe_type,
                probe_name=self.config.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Timeout after {self.config.timeout_seconds}s",
                duration_ms=self.config.timeout_seconds * 1000
            )
            return self.last_result

        except Exception as e:
            self.consecutive_failures += 1
            self.last_result = ProbeResult(
                probe_type=self.config.probe_type,
                probe_name=self.config.name,
                status=HealthStatus.UNHEALTHY,
                message=str(e),
                duration_ms=(time.time() - start) * 1000
            )
            return self.last_result

    def is_healthy(self) -> bool:
        """Check if probe is considered healthy."""
        if self.consecutive_successes < self.config.success_threshold:
            return False
        if self.consecutive_failures >= self.config.failure_threshold:
            return False
        return True

    def enable(self):
        """Enable the probe."""
        self._enabled = True

    def disable(self):
        """Disable the probe."""
        self._enabled = False


class HealthCheckEngine:
    """Central health check engine."""

    def __init__(self, service_name: str = "pilotsuite-core"):
        self.service_name = service_name
        self._probes: Dict[str, HealthProbe] = {}
        self._dependency_checks = DependencyCheck()
        self._startup_complete = False
        self._last_health_check: Optional[float] = None

    def register_probe(self, config: ProbeConfig):
        """Register a health probe."""
        probe = HealthProbe(config)
        self._probes[config.name] = probe
        logger.info(f"Registered {config.probe_type.value} probe: {config.name}")

    def register_dependency(self, name: str, check_fn: Callable):
        """Register dependency check."""
        self._dependency_checks.register_check(name, check_fn)

    async def run_probe(self, probe_name: str) -> ProbeResult:
        """Run specific probe."""
        if probe_name not in self._probes:
            return ProbeResult(
                probe_type=ProbeType.LIVENESS,
                probe_name=probe_name,
                status=HealthStatus.UNKNOWN,
                message=f"Unknown probe: {probe_name}"
            )
        return await self._probes[probe_name].run()

    async def run_all_probes(self, probe_type: Optional[ProbeType] = None) -> List[ProbeResult]:
        """Run all probes (optionally filtered by type)."""
        results = []
        for name, probe in self._probes.items():
            if probe_type is None or probe.config.probe_type == probe_type:
                result = await probe.run()
                results.append(result)
        self._last_health_check = time.time()
        return results

    async def check_dependencies(self) -> Dict[str, ProbeResult]:
        """Check all dependencies."""
        return await self._dependency_checks.check_all()

    def get_overall_status(self) -> Tuple[HealthStatus, Dict[str, Any]]:
        """Get overall health status."""
        liveness_healthy = True
        readiness_healthy = True
        startup_healthy = True

        details = {
            "service": self.service_name,
            "timestamp": time.time(),
            "startup_complete": self._startup_complete,
            "probes": {}
        }

        for name, probe in self._probes.items():
            is_healthy = probe.is_healthy()
            details["probes"][name] = {
                "type": probe.config.probe_type.value,
                "healthy": is_healthy,
                "consecutive_failures": probe.consecutive_failures,
                "consecutive_successes": probe.consecutive_successes,
            }

            if probe.config.probe_type == ProbeType.LIVENESS and not is_healthy:
                liveness_healthy = False
            elif probe.config.probe_type == ProbeType.READINESS and not is_healthy:
                readiness_healthy = False
            elif probe.config.probe_type == ProbeType.STARTUP and not is_healthy:
                startup_healthy = False

        # Determine overall status
        if not liveness_healthy:
            overall = HealthStatus.UNHEALTHY
        elif not readiness_healthy:
            overall = HealthStatus.DEGRADED
        elif not startup_healthy:
            overall = HealthStatus.UNHEALTHY
        else:
            overall = HealthStatus.HEALTHY

        return overall, details

    def mark_startup_complete(self):
        """Mark startup as complete."""
        self._startup_complete = True
        logger.info("Startup complete - marking health as ready")

    def get_health_response(self) -> Dict[str, Any]:
        """Get health check response for API."""
        status, details = self.get_overall_status()
        return {
            "status": status.value,
            "service": self.service_name,
            "timestamp": details["timestamp"],
            "startup_complete": self._startup_complete,
            "probes": details["probes"],
            "dependencies": {
                name: {
                    "status": result.status.value,
                    "message": result.message,
                    "duration_ms": result.duration_ms
                }
                for name, result in self._dependency_checks.get_results().items()
            }
        }


# Global default health check engine
default_health_engine: Optional[HealthCheckEngine] = None


def init_health_engine(service_name: str = "pilotsuite-core") -> HealthCheckEngine:
    """Initialize global health check engine."""
    global default_health_engine
    default_health_engine = HealthCheckEngine(service_name)
    return default_health_engine


# Convenience decorators for probe registration
def liveness_probe(name: str, timeout: float = 5.0):
    """Decorator for liveness probe."""
    def decorator(func):
        config = ProbeConfig(
            name=name,
            probe_type=ProbeType.LIVENESS,
            check_fn=func,
            timeout_seconds=timeout
        )
        if default_health_engine:
            default_health_engine.register_probe(config)
        return func
    return decorator


def readiness_probe(name: str, timeout: float = 5.0):
    """Decorator for readiness probe."""
    def decorator(func):
        config = ProbeConfig(
            name=name,
            probe_type=ProbeType.READINESS,
            check_fn=func,
            timeout_seconds=timeout
        )
        if default_health_engine:
            default_health_engine.register_probe(config)
        return func
    return decorator


def startup_probe(name: str, timeout: float = 30.0):
    """Decorator for startup probe."""
    def decorator(func):
        config = ProbeConfig(
            name=name,
            probe_type=ProbeType.STARTUP,
            check_fn=func,
            timeout_seconds=timeout
        )
        if default_health_engine:
            default_health_engine.register_probe(config)
        return func
    return decorator
