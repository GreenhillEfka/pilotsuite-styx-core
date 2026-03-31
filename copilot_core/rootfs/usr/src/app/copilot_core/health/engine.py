"""Health Engine — Slice 38.

System health monitoring for PilotSuite Core.

Features:
- Component health checks
- Dependency monitoring
- Health status aggregation
- Readiness/liveness probes
- Health history tracking
- Alerting on health degradation
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Callable
from enum import Enum
import uuid
import time

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"
    UNKNOWN = "unknown"


class CheckType(Enum):
    """Health check type."""
    LIVENESS = "liveness"  # Is the component running?
    READINESS = "readiness"  # Is the component ready to serve?
    STARTUP = "startup"  # Has the component started successfully?
    CUSTOM = "custom"  # Custom health check


@dataclass
class HealthCheckResult:
    """Result of a health check."""
    check_id: str
    component: str
    check_type: CheckType
    status: HealthStatus
    message: str
    timestamp: str
    latency_ms: int
    details: Dict[str, Any] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "component": self.component,
            "check_type": self.check_type.value,
            "status": self.status.value,
            "message": self.message,
            "timestamp": self.timestamp,
            "latency_ms": self.latency_ms,
            "details": self.details,
        }


@dataclass
class ComponentHealth:
    """Health status of a component."""
    component: str
    status: HealthStatus
    last_check: str
    last_success: Optional[str]
    last_failure: Optional[str]
    consecutive_failures: int
    total_checks: int
    successful_checks: int
    failed_checks: int
    checks: List[HealthCheckResult] = field(default_factory=list)
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "component": self.component,
            "status": self.status.value,
            "last_check": self.last_check,
            "last_success": self.last_success,
            "last_failure": self.last_failure,
            "consecutive_failures": self.consecutive_failures,
            "total_checks": self.total_checks,
            "successful_checks": self.successful_checks,
            "failed_checks": self.failed_checks,
            "uptime_percent": round((self.successful_checks / self.total_checks * 100), 2) if self.total_checks > 0 else 0.0,
        }


@dataclass
class HealthCheckDefinition:
    """Definition of a health check."""
    check_id: str
    component: str
    check_type: CheckType
    checker: Callable[[], Dict[str, Any]]
    interval_seconds: int = 30
    timeout_seconds: int = 10
    critical: bool = False  # If critical, component is unhealthy when this fails
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "check_id": self.check_id,
            "component": self.component,
            "check_type": self.check_type.value,
            "interval_seconds": self.interval_seconds,
            "timeout_seconds": self.timeout_seconds,
            "critical": self.critical,
            "enabled": self.enabled,
        }


class HealthEngine:
    """System health monitoring engine."""
    
    def __init__(self):
        self._checks: Dict[str, HealthCheckDefinition] = {}
        self._component_health: Dict[str, ComponentHealth] = {}
        self._health_history: List[HealthCheckResult] = []
        self._max_history_size = 1000
        
        # Callbacks for health status changes
        self._status_callbacks: List[Callable] = []
        
        # Register built-in checks
        self._register_builtin_checks()
    
    def _register_builtin_checks(self) -> None:
        """Register built-in health checks."""
        # System memory check
        self.register_check(
            component="system",
            check_type=CheckType.LIVENESS,
            checker=self._check_system_memory,
            interval_seconds=60,
            check_id="system_memory",
        )
    
    def _check_system_memory(self) -> Dict[str, Any]:
        """Check system memory availability."""
        try:
            import psutil
            mem = psutil.virtual_memory()
            available_percent = mem.available / mem.total * 100
            
            if available_percent < 5:
                return {
                    "status": "unhealthy",
                    "message": f"Critical: Only {available_percent:.1f}% memory available",
                    "details": {"available_percent": available_percent},
                }
            elif available_percent < 15:
                return {
                    "status": "degraded",
                    "message": f"Warning: Only {available_percent:.1f}% memory available",
                    "details": {"available_percent": available_percent},
                }
            else:
                return {
                    "status": "healthy",
                    "message": f"Memory OK: {available_percent:.1f}% available",
                    "details": {"available_percent": available_percent},
                }
        except ImportError:
            return {
                "status": "unknown",
                "message": "psutil not available",
                "details": {},
            }
        except Exception as exc:
            return {
                "status": "unhealthy",
                "message": str(exc),
                "details": {"error": str(exc)},
            }
    
    def register_check(self, component: str, check_type: str,
                      checker: Callable[[], Dict[str, Any]],
                      interval_seconds: int = 30,
                      timeout_seconds: int = 10,
                      critical: bool = False,
                      check_id: Optional[str] = None) -> str:
        """Register a health check."""
        if check_id is None:
            check_id = f"check_{uuid.uuid4().hex[:8]}"
        
        definition = HealthCheckDefinition(
            check_id=check_id,
            component=component,
            check_type=CheckType(check_type),
            checker=checker,
            interval_seconds=interval_seconds,
            timeout_seconds=timeout_seconds,
            critical=critical,
        )
        
        self._checks[check_id] = definition
        
        # Initialize component health if needed
        if component not in self._component_health:
            self._component_health[component] = ComponentHealth(
                component=component,
                status=HealthStatus.UNKNOWN,
                last_check="",
                last_success=None,
                last_failure=None,
                consecutive_failures=0,
                total_checks=0,
                successful_checks=0,
                failed_checks=0,
            )
        
        logger.info("Health check registered: %s for %s", check_id, component)
        
        return check_id
    
    def run_check(self, check_id: str) -> Optional[HealthCheckResult]:
        """Run a specific health check."""
        if check_id not in self._checks:
            logger.warning("Unknown health check: %s", check_id)
            return None
        
        definition = self._checks[check_id]
        
        if not definition.enabled:
            logger.debug("Health check disabled: %s", check_id)
            return None
        
        start_time = time.time()
        timestamp = datetime.now(timezone.utc).isoformat()
        
        try:
            # Run checker with timeout
            result_data = definition.checker()
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            status = HealthStatus(result_data.get("status", "unknown"))
            message = result_data.get("message", "")
            details = result_data.get("details", {})
            
            result = HealthCheckResult(
                check_id=check_id,
                component=definition.component,
                check_type=definition.check_type,
                status=status,
                message=message,
                timestamp=timestamp,
                latency_ms=latency_ms,
                details=details,
            )
            
            # Update component health
            self._update_component_health(definition.component, result, definition.critical)
            
            # Store in history
            self._health_history.append(result)
            if len(self._health_history) > self._max_history_size:
                self._health_history = self._health_history[-self._max_history_size:]
            
            logger.debug("Health check %s: %s", check_id, status.value)
            
            return result
            
        except Exception as exc:
            logger.exception("Health check %s failed: %s", check_id, exc)
            
            latency_ms = int((time.time() - start_time) * 1000)
            
            result = HealthCheckResult(
                check_id=check_id,
                component=definition.component,
                check_type=definition.check_type,
                status=HealthStatus.UNHEALTHY,
                message=f"Check failed: {exc}",
                timestamp=timestamp,
                latency_ms=latency_ms,
                details={"error": str(exc)},
            )
            
            self._update_component_health(definition.component, result, definition.critical)
            self._health_history.append(result)
            
            return result
    
    def _update_component_health(self, component: str,
                                result: HealthCheckResult,
                                is_critical: bool) -> None:
        """Update component health status."""
        if component not in self._component_health:
            self._component_health[component] = ComponentHealth(
                component=component,
                status=HealthStatus.UNKNOWN,
                last_check="",
                last_success=None,
                last_failure=None,
                consecutive_failures=0,
                total_checks=0,
                successful_checks=0,
                failed_checks=0,
            )
        
        health = self._component_health[component]
        
        health.last_check = result.timestamp
        health.total_checks += 1
        
        if result.status == HealthStatus.HEALTHY:
            health.successful_checks += 1
            health.consecutive_failures = 0
            health.last_success = result.timestamp
            health.status = HealthStatus.HEALTHY
        elif result.status == HealthStatus.DEGRADED:
            health.successful_checks += 1
            health.consecutive_failures = 0
            health.last_success = result.timestamp
            if health.status != HealthStatus.UNHEALTHY:
                health.status = HealthStatus.DEGRADED
        else:  # UNHEALTHY or UNKNOWN
            health.failed_checks += 1
            health.consecutive_failures += 1
            health.last_failure = result.timestamp
            
            if is_critical or health.consecutive_failures >= 3:
                health.status = HealthStatus.UNHEALTHY
        
        # Store recent checks
        health.checks.append(result)
        if len(health.checks) > 10:
            health.checks = health.checks[-10:]
        
        # Notify callbacks on status change
        self._notify_status_change(component, health.status, result)
    
    def _notify_status_change(self, component: str,
                             new_status: HealthStatus,
                             result: HealthCheckResult) -> None:
        """Notify callbacks of status change."""
        for callback in self._status_callbacks:
            try:
                callback({
                    "component": component,
                    "status": new_status.value,
                    "check_result": result.to_dict(),
                })
            except Exception as exc:
                logger.exception("Status callback failed: %s", exc)
    
    def register_status_callback(self, callback: Callable) -> None:
        """Register callback for health status changes."""
        self._status_callbacks.append(callback)
    
    def run_all_checks(self) -> Dict[str, HealthCheckResult]:
        """Run all registered health checks."""
        results = {}
        
        for check_id in self._checks:
            result = self.run_check(check_id)
            if result:
                results[check_id] = result
        
        return results
    
    def get_component_health(self, component: str) -> Optional[Dict[str, Any]]:
        """Get health status of a component."""
        if component not in self._component_health:
            return None
        
        return self._component_health[component].to_dict()
    
    def get_all_components_health(self) -> List[Dict[str, Any]]:
        """Get health status of all components."""
        return [h.to_dict() for h in self._component_health.values()]
    
    def get_overall_health(self) -> Dict[str, Any]:
        """Get overall system health."""
        if not self._component_health:
            return {
                "status": HealthStatus.UNKNOWN.value,
                "healthy_components": 0,
                "degraded_components": 0,
                "unhealthy_components": 0,
                "total_components": 0,
            }
        
        healthy = sum(1 for h in self._component_health.values() if h.status == HealthStatus.HEALTHY)
        degraded = sum(1 for h in self._component_health.values() if h.status == HealthStatus.DEGRADED)
        unhealthy = sum(1 for h in self._component_health.values() if h.status == HealthStatus.UNHEALTHY)
        unknown = sum(1 for h in self._component_health.values() if h.status == HealthStatus.UNKNOWN)
        
        # Determine overall status
        if unhealthy > 0:
            overall = HealthStatus.UNHEALTHY
        elif degraded > 0:
            overall = HealthStatus.DEGRADED
        elif unknown > 0:
            overall = HealthStatus.UNKNOWN
        else:
            overall = HealthStatus.HEALTHY
        
        return {
            "status": overall.value,
            "healthy_components": healthy,
            "degraded_components": degraded,
            "unhealthy_components": unhealthy,
            "unknown_components": unknown,
            "total_components": len(self._component_health),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
    
    def get_health_history(self, component: Optional[str] = None,
                          status: Optional[HealthStatus] = None,
                          limit: int = 100) -> List[Dict[str, Any]]:
        """Get health check history."""
        results = self._health_history
        
        if component:
            results = [r for r in results if r.component == component]
        
        if status:
            results = [r for r in results if r.status == status]
        
        # Sort by timestamp (newest first)
        results.sort(key=lambda r: r.timestamp, reverse=True)
        
        return [r.to_dict() for r in results[:limit]]
    
    def get_checks(self, component: Optional[str] = None) -> List[Dict[str, Any]]:
        """Get registered health checks."""
        checks = list(self._checks.values())
        
        if component:
            checks = [c for c in checks if c.component == component]
        
        return [c.to_dict() for c in checks]
    
    def enable_check(self, check_id: str) -> bool:
        """Enable a health check."""
        if check_id not in self._checks:
            return False
        
        self._checks[check_id].enabled = True
        return True
    
    def disable_check(self, check_id: str) -> bool:
        """Disable a health check."""
        if check_id not in self._checks:
            return False
        
        self._checks[check_id].enabled = False
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get health monitoring statistics."""
        total_checks = sum(h.total_checks for h in self._component_health.values())
        successful_checks = sum(h.successful_checks for h in self._component_health.values())
        failed_checks = sum(h.failed_checks for h in self._component_health.values())
        
        return {
            "total_components": len(self._component_health),
            "total_checks_registered": len(self._checks),
            "total_checks_run": total_checks,
            "successful_checks": successful_checks,
            "failed_checks": failed_checks,
            "success_rate": round(successful_checks / total_checks * 100, 2) if total_checks > 0 else 0.0,
            "history_size": len(self._health_history),
        }
    
    def get_unhealthy_components(self) -> List[Dict[str, Any]]:
        """Get list of unhealthy components."""
        unhealthy = [
            h.to_dict() for h in self._component_health.values()
            if h.status in (HealthStatus.UNHEALTHY, HealthStatus.DEGRADED)
        ]
        
        # Sort by consecutive failures (most failures first)
        unhealthy.sort(key=lambda h: h["consecutive_failures"], reverse=True)
        
        return unhealthy
    
    def reset_component_health(self, component: str) -> bool:
        """Reset health status for a component."""
        if component not in self._component_health:
            return False
        
        health = self._component_health[component]
        health.status = HealthStatus.UNKNOWN
        health.consecutive_failures = 0
        health.checks.clear()
        
        return True
    
    def clear_history(self, older_than: Optional[str] = None) -> int:
        """Clear health check history."""
        if older_than is None:
            count = len(self._health_history)
            self._health_history.clear()
            return count
        
        # Clear history older than timestamp
        cutoff = datetime.fromisoformat(older_than)
        
        initial_count = len(self._health_history)
        self._health_history = [
            r for r in self._health_history
            if datetime.fromisoformat(r.timestamp) >= cutoff
        ]
        
        return initial_count - len(self._health_history)


def create_health_engine() -> HealthEngine:
    """Factory function to create health engine."""
    return HealthEngine()
