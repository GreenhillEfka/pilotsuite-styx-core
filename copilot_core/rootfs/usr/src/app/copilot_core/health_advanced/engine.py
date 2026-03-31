"""Health Advanced Engine — Slice 60.

Advanced health checking for PilotSuite Core.

Features:
- Multi-level health checks (critical, warning, info)
- Dependency health tracking
- Health aggregation
- Circuit breaker integration
- Health history
- Alerting thresholds
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable, Set
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status levels."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CheckType(Enum):
    """Health check types."""
    HTTP = "http"
    TCP = "tcp"
    DATABASE = "database"
    CACHE = "cache"
    QUEUE = "queue"
    CUSTOM = "custom"
    MEMORY = "memory"
    DISK = "disk"
    CPU = "cpu"


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    check_id: str
    name: str
    status: HealthStatus
    message: str
    response_time_ms: Optional[float] = None
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    metadata: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "status": self.status.value,
            "message": self.message,
            "response_time_ms": self.response_time_ms,
            "timestamp": self.timestamp,
            "metadata": self.metadata,
        }


@dataclass
class HealthCheck:
    """Health check definition."""
    check_id: str
    name: str
    check_type: CheckType
    handler: Optional[Callable[[], HealthCheckResult]]
    critical: bool = True
    timeout_seconds: float = 10.0
    interval_seconds: int = 30
    dependencies: List[str] = field(default_factory=list)
    thresholds: Dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    last_result: Optional[HealthCheckResult] = None
    consecutive_failures: int = 0
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "name": self.name,
            "check_type": self.check_type.value,
            "critical": self.critical,
            "timeout_seconds": self.timeout_seconds,
            "interval_seconds": self.interval_seconds,
            "dependencies": self.dependencies,
            "thresholds": self.thresholds,
            "enabled": self.enabled,
            "consecutive_failures": self.consecutive_failures,
            "last_result": self.last_result.to_dict() if self.last_result else None,
            "created_at": self.created_at,
        }


@dataclass
class HealthAggregation:
    """Aggregated health status."""
    overall_status: HealthStatus
    total_checks: int
    healthy_checks: int
    degraded_checks: int
    unhealthy_checks: int
    unknown_checks: int
    critical_healthy: int
    critical_unhealthy: int
    checks: List[HealthCheckResult] = field(default_factory=list)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_status": self.overall_status.value,
            "total_checks": self.total_checks,
            "healthy_checks": self.healthy_checks,
            "degraded_checks": self.degraded_checks,
            "unhealthy_checks": self.unhealthy_checks,
            "unknown_checks": self.unknown_checks,
            "critical_healthy": self.critical_healthy,
            "critical_unhealthy": self.critical_unhealthy,
            "checks": [c.to_dict() for c in self.checks],
            "timestamp": self.timestamp,
        }


class HealthEngine:
    """Advanced health checking engine."""
    
    def __init__(self):
        self._checks: Dict[str, HealthCheck] = {}
        self._history: Dict[str, List[HealthCheckResult]] = {}
        self._listeners: List[Callable[[str, HealthCheckResult], None]] = []
        self._running = False
        self._monitor_thread: Optional[threading.Thread] = None
        self._lock = threading.Lock()
        
        # Statistics
        self._stats = {
            "total_checks_run": 0,
            "total_healthy": 0,
            "total_degraded": 0,
            "total_unhealthy": 0,
            "by_check": {},
        }
    
    def start_monitoring(self, interval_seconds: int = 30) -> None:
        """Start background health monitoring."""
        self._running = True
        self._monitor_thread = threading.Thread(
            target=self._monitor_loop,
            args=(interval_seconds,),
            daemon=True,
        )
        self._monitor_thread.start()
        logger.info("Health monitoring started")
    
    def stop_monitoring(self) -> None:
        """Stop background health monitoring."""
        self._running = False
        if self._monitor_thread:
            self._monitor_thread.join(timeout=5)
        logger.info("Health monitoring stopped")
    
    def register_check(self, name: str, check_type: CheckType,
                      handler: Callable[[], HealthCheckResult],
                      critical: bool = True,
                      timeout_seconds: float = 10.0,
                      interval_seconds: int = 30,
                      dependencies: Optional[List[str]] = None,
                      thresholds: Optional[Dict[str, Any]] = None) -> str:
        """Register a health check."""
        check_id = f"hc_{uuid.uuid4().hex[:16]}"
        
        check = HealthCheck(
            check_id=check_id,
            name=name,
            check_type=check_type,
            handler=handler,
            critical=critical,
            timeout_seconds=timeout_seconds,
            interval_seconds=interval_seconds,
            dependencies=dependencies or [],
            thresholds=thresholds or {},
        )
        
        with self._lock:
            self._checks[check_id] = check
            self._history[check_id] = []
        
        logger.info("Health check registered: %s (%s)", name, check_id)
        
        return check_id
    
    def register_http_check(self, name: str, url: str,
                           critical: bool = True,
                           timeout_seconds: float = 5.0,
                           expected_status: int = 200) -> str:
        """Register an HTTP health check."""
        def handler() -> HealthCheckResult:
            import urllib.request
            import urllib.error
            
            start = time.time()
            
            try:
                response = urllib.request.urlopen(url, timeout=timeout_seconds)
                response_time = (time.time() - start) * 1000
                
                if response.status == expected_status:
                    return HealthCheckResult(
                        check_id="",
                        name=name,
                        status=HealthStatus.HEALTHY,
                        message=f"HTTP {response.status}",
                        response_time_ms=response_time,
                    )
                else:
                    return HealthCheckResult(
                        check_id="",
                        name=name,
                        status=HealthStatus.UNHEALTHY,
                        message=f"HTTP {response.status} (expected {expected_status})",
                        response_time_ms=response_time,
                    )
                    
            except Exception as e:
                response_time = (time.time() - start) * 1000
                return HealthCheckResult(
                    check_id="",
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=str(e),
                    response_time_ms=response_time,
                )
        
        return self.register_check(
            name=name,
            check_type=CheckType.HTTP,
            handler=handler,
            critical=critical,
            timeout_seconds=timeout_seconds,
        )
    
    def register_tcp_check(self, name: str, host: str, port: int,
                          critical: bool = True,
                          timeout_seconds: float = 5.0) -> str:
        """Register a TCP health check."""
        def handler() -> HealthCheckResult:
            import socket
            
            start = time.time()
            
            try:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.settimeout(timeout_seconds)
                result = sock.connect_ex((host, port))
                sock.close()
                
                response_time = (time.time() - start) * 1000
                
                if result == 0:
                    return HealthCheckResult(
                        check_id="",
                        name=name,
                        status=HealthStatus.HEALTHY,
                        message=f"TCP {host}:{port} reachable",
                        response_time_ms=response_time,
                    )
                else:
                    return HealthCheckResult(
                        check_id="",
                        name=name,
                        status=HealthStatus.UNHEALTHY,
                        message=f"TCP {host}:{port} unreachable",
                        response_time_ms=response_time,
                    )
                    
            except Exception as e:
                response_time = (time.time() - start) * 1000
                return HealthCheckResult(
                    check_id="",
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=str(e),
                    response_time_ms=response_time,
                )
        
        return self.register_check(
            name=name,
            check_type=CheckType.TCP,
            handler=handler,
            critical=critical,
            timeout_seconds=timeout_seconds,
        )
    
    def register_memory_check(self, name: str,
                             warning_threshold: float = 0.8,
                             critical_threshold: float = 0.9,
                             critical: bool = True) -> str:
        """Register a memory usage check."""
        def handler() -> HealthCheckResult:
            import psutil
            
            mem = psutil.virtual_memory()
            usage = mem.percent / 100.0
            
            if usage >= critical_threshold:
                return HealthCheckResult(
                    check_id="",
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=f"Memory usage critical: {usage*100:.1f}%",
                    metadata={"usage_percent": usage * 100, "available_mb": mem.available / 1024 / 1024},
                )
            elif usage >= warning_threshold:
                return HealthCheckResult(
                    check_id="",
                    name=name,
                    status=HealthStatus.DEGRADED,
                    message=f"Memory usage warning: {usage*100:.1f}%",
                    metadata={"usage_percent": usage * 100, "available_mb": mem.available / 1024 / 1024},
                )
            else:
                return HealthCheckResult(
                    check_id="",
                    name=name,
                    status=HealthStatus.HEALTHY,
                    message=f"Memory usage normal: {usage*100:.1f}%",
                    metadata={"usage_percent": usage * 100, "available_mb": mem.available / 1024 / 1024},
                )
        
        return self.register_check(
            name=name,
            check_type=CheckType.MEMORY,
            handler=handler,
            critical=critical,
            thresholds={
                "warning": warning_threshold,
                "critical": critical_threshold,
            },
        )
    
    def register_disk_check(self, name: str, path: str = "/",
                           warning_threshold: float = 0.8,
                           critical_threshold: float = 0.9,
                           critical: bool = True) -> str:
        """Register a disk usage check."""
        def handler() -> HealthCheckResult:
            import psutil
            
            try:
                disk = psutil.disk_usage(path)
                usage = disk.percent / 100.0
                
                if usage >= critical_threshold:
                    return HealthCheckResult(
                        check_id="",
                        name=name,
                        status=HealthStatus.UNHEALTHY,
                        message=f"Disk usage critical: {usage*100:.1f}%",
                        metadata={"usage_percent": usage * 100, "free_gb": disk.free / 1024 / 1024 / 1024},
                    )
                elif usage >= warning_threshold:
                    return HealthCheckResult(
                        check_id="",
                        name=name,
                        status=HealthStatus.DEGRADED,
                        message=f"Disk usage warning: {usage*100:.1f}%",
                        metadata={"usage_percent": usage * 100, "free_gb": disk.free / 1024 / 1024 / 1024},
                    )
                else:
                    return HealthCheckResult(
                        check_id="",
                        name=name,
                        status=HealthStatus.HEALTHY,
                        message=f"Disk usage normal: {usage*100:.1f}%",
                        metadata={"usage_percent": usage * 100, "free_gb": disk.free / 1024 / 1024 / 1024},
                    )
            except Exception as e:
                return HealthCheckResult(
                    check_id="",
                    name=name,
                    status=HealthStatus.UNHEALTHY,
                    message=str(e),
                )
        
        return self.register_check(
            name=name,
            check_type=CheckType.DISK,
            handler=handler,
            critical=critical,
            thresholds={
                "warning": warning_threshold,
                "critical": critical_threshold,
            },
        )
    
    def unregister_check(self, check_id: str) -> bool:
        """Unregister a health check."""
        with self._lock:
            if check_id not in self._checks:
                return False
            
            del self._checks[check_id]
            
            if check_id in self._history:
                del self._history[check_id]
        
        logger.info("Health check unregistered: %s", check_id)
        
        return True
    
    def run_check(self, check_id: str) -> Optional[HealthCheckResult]:
        """Run a specific health check."""
        with self._lock:
            check = self._checks.get(check_id)
            
            if not check or not check.enabled:
                return None
            
            # Check dependencies
            if not self._check_dependencies(check):
                result = HealthCheckResult(
                    check_id=check_id,
                    name=check.name,
                    status=HealthStatus.UNHEALTHY,
                    message="Dependencies not healthy",
                )
                self._record_result(check_id, result)
                return result
        
        # Run handler with timeout
        result = self._run_with_timeout(check)
        result.check_id = check_id
        
        # Record result
        self._record_result(check_id, result)
        
        return result
    
    def _run_with_timeout(self, check: HealthCheck) -> HealthCheckResult:
        """Run check handler with timeout."""
        result_container = {"result": None}
        error_container = {"error": None}
        
        def run_handler():
            try:
                result_container["result"] = check.handler()
            except Exception as e:
                error_container["error"] = e
        
        thread = threading.Thread(target=run_handler)
        thread.start()
        thread.join(timeout=check.timeout_seconds)
        
        if thread.is_alive():
            return HealthCheckResult(
                check_id=check.check_id,
                name=check.name,
                status=HealthStatus.UNHEALTHY,
                message=f"Check timed out after {check.timeout_seconds}s",
            )
        
        if error_container["error"]:
            return HealthCheckResult(
                check_id=check.check_id,
                name=check.name,
                status=HealthStatus.UNHEALTHY,
                message=str(error_container["error"]),
            )
        
        if result_container["result"]:
            return result_container["result"]
        
        return HealthCheckResult(
            check_id=check.check_id,
            name=check.name,
            status=HealthStatus.UNKNOWN,
            message="No result from handler",
        )
    
    def _check_dependencies(self, check: HealthCheck) -> bool:
        """Check if all dependencies are healthy."""
        for dep_id in check.dependencies:
            dep_check = self._checks.get(dep_id)
            
            if not dep_check:
                return False
            
            if not dep_check.last_result:
                return False
            
            if dep_check.last_result.status != HealthStatus.HEALTHY:
                return False
        
        return True
    
    def _record_result(self, check_id: str, result: HealthCheckResult) -> None:
        """Record check result."""
        with self._lock:
            check = self._checks.get(check_id)
            
            if not check:
                return
            
            check.last_result = result
            
            # Update consecutive failures
            if result.status == HealthStatus.UNHEALTHY:
                check.consecutive_failures += 1
            else:
                check.consecutive_failures = 0
            
            # Update statistics
            self._stats["total_checks_run"] += 1
            self._stats[f"total_{result.status.value}"] = self._stats.get(f"total_{result.status.value}", 0) + 1
            self._stats["by_check"][check_id] = self._stats["by_check"].get(check_id, 0) + 1
            
            # Record history
            self._history[check_id].append(result)
            
            # Limit history size
            if len(self._history[check_id]) > 100:
                self._history[check_id] = self._history[check_id][-100:]
        
        # Notify listeners
        for listener in self._listeners:
            try:
                listener(check_id, result)
            except Exception as e:
                logger.exception("Health listener failed: %s", e)
    
    def _monitor_loop(self, interval_seconds: int) -> None:
        """Background monitoring loop."""
        while self._running:
            try:
                self._run_all_checks()
            except Exception as e:
                logger.exception("Monitor loop error: %s", e)
            
            time.sleep(interval_seconds)
    
    def _run_all_checks(self) -> None:
        """Run all enabled checks."""
        with self._lock:
            checks_to_run = [
                check for check in self._checks.values()
                if check.enabled
            ]
        
        for check in checks_to_run:
            try:
                self.run_check(check.check_id)
            except Exception as e:
                logger.exception("Check failed: %s", e)
    
    def get_health(self) -> HealthAggregation:
        """Get aggregated health status."""
        with self._lock:
            checks = list(self._checks.values())
        
        healthy = 0
        degraded = 0
        unhealthy = 0
        unknown = 0
        critical_healthy = 0
        critical_unhealthy = 0
        results = []
        
        for check in checks:
            if check.last_result:
                results.append(check.last_result)
                
                if check.last_result.status == HealthStatus.HEALTHY:
                    healthy += 1
                    if check.critical:
                        critical_healthy += 1
                elif check.last_result.status == HealthStatus.DEGRADED:
                    degraded += 1
                elif check.last_result.status == HealthStatus.UNHEALTHY:
                    unhealthy += 1
                    if check.critical:
                        critical_unhealthy += 1
                else:
                    unknown += 1
            else:
                unknown += 1
        
        # Determine overall status
        if critical_unhealthy > 0:
            overall = HealthStatus.UNHEALTHY
        elif unhealthy > 0 or degraded > 0:
            overall = HealthStatus.DEGRADED
        elif unknown == len(checks):
            overall = HealthStatus.UNKNOWN
        else:
            overall = HealthStatus.HEALTHY
        
        return HealthAggregation(
            overall_status=overall,
            total_checks=len(checks),
            healthy_checks=healthy,
            degraded_checks=degraded,
            unhealthy_checks=unhealthy,
            unknown_checks=unknown,
            critical_healthy=critical_healthy,
            critical_unhealthy=critical_unhealthy,
            checks=results,
        )
    
    def get_check_status(self, check_id: str) -> Optional[HealthCheckResult]:
        """Get status of specific check."""
        with self._lock:
            check = self._checks.get(check_id)
            
            if not check:
                return None
            
            return check.last_result
    
    def get_check_history(self, check_id: str,
                         limit: int = 10) -> List[HealthCheckResult]:
        """Get history for specific check."""
        with self._lock:
            history = self._history.get(check_id, [])
            return history[-limit:]
    
    def enable_check(self, check_id: str) -> bool:
        """Enable a health check."""
        with self._lock:
            check = self._checks.get(check_id)
            
            if not check:
                return False
            
            check.enabled = True
            return True
    
    def disable_check(self, check_id: str) -> bool:
        """Disable a health check."""
        with self._lock:
            check = self._checks.get(check_id)
            
            if not check:
                return False
            
            check.enabled = False
            return True
    
    def add_listener(self, listener: Callable[[str, HealthCheckResult], None]) -> None:
        """Add health status listener."""
        self._listeners.append(listener)
    
    def remove_listener(self, listener: Callable[[str, HealthCheckResult], None]) -> bool:
        """Remove health status listener."""
        if listener in self._listeners:
            self._listeners.remove(listener)
            return True
        return False
    
    def reset_check_failures(self, check_id: str) -> bool:
        """Reset consecutive failure count."""
        with self._lock:
            check = self._checks.get(check_id)
            
            if not check:
                return False
            
            check.consecutive_failures = 0
            return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get health statistics."""
        with self._lock:
            return {
                **self._stats,
                "total_checks": len(self._checks),
                "enabled_checks": len([c for c in self._checks.values() if c.enabled]),
                "critical_checks": len([c for c in self._checks.values() if c.critical]),
            }
    
    def clear_history(self, check_id: Optional[str] = None) -> int:
        """Clear check history."""
        with self._lock:
            if check_id:
                if check_id in self._history:
                    count = len(self._history[check_id])
                    self._history[check_id] = []
                    return count
                return 0
            else:
                count = sum(len(h) for h in self._history.values())
                for key in self._history:
                    self._history[key] = []
                return count


def create_health_engine() -> HealthEngine:
    """Factory function to create health engine."""
    return HealthEngine()
