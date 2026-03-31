"""Health Check & System Monitoring — Slice 24.

System health monitoring for PilotSuite Core.

Features:
- System resource monitoring (CPU, memory, disk)
- Service health checks
- Dependency monitoring
- Alerting on threshold breaches
- Health score calculation
- Performance trending
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class HealthStatus(Enum):
    """Health status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    WARNING = "warning"
    CRITICAL = "critical"
    UNKNOWN = "unknown"


class ComponentType(Enum):
    """System component type."""
    CPU = "cpu"
    MEMORY = "memory"
    DISK = "disk"
    NETWORK = "network"
    SERVICE = "service"
    DATABASE = "database"
    EXTERNAL_API = "external_api"


@dataclass
class ComponentHealth:
    """Health status of a single component."""
    component_id: str
    component_type: ComponentType
    name: str
    status: HealthStatus
    value: float  # Current value (percentage, latency, etc.)
    threshold_warning: float
    threshold_critical: float
    unit: str = "%"
    last_check: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "component_id": self.component_id,
            "component_type": self.component_type.value,
            "name": self.name,
            "status": self.status.value,
            "value": self.value,
            "threshold_warning": self.threshold_warning,
            "threshold_critical": self.threshold_critical,
            "unit": self.unit,
            "last_check": self.last_check,
            "message": self.message,
        }


@dataclass
class SystemHealth:
    """Overall system health."""
    timestamp: str
    overall_status: HealthStatus
    health_score: float  # 0-100
    components: Dict[str, ComponentHealth]
    warnings: List[str]
    critical_issues: List[str]
    recommendations: List[str]
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp,
            "overall_status": self.overall_status.value,
            "health_score": self.health_score,
            "components": {k: v.to_dict() for k, v in self.components.items()},
            "warnings": self.warnings,
            "critical_issues": self.critical_issues,
            "recommendations": self.recommendations,
        }


@dataclass
class HealthAlert:
    """Health alert."""
    alert_id: str
    component_id: str
    severity: HealthStatus
    title: str
    message: str
    value: float
    threshold: float
    acknowledged: bool = False
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    acknowledged_at: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "alert_id": self.alert_id,
            "component_id": self.component_id,
            "severity": self.severity.value,
            "title": self.title,
            "message": self.message,
            "value": self.value,
            "threshold": self.threshold,
            "acknowledged": self.acknowledged,
            "created_at": self.created_at,
            "acknowledged_at": self.acknowledged_at,
        }


class HealthCheckEngine:
    """Health check and monitoring engine."""
    
    def __init__(self):
        self._components: Dict[str, ComponentHealth] = {}
        self._alerts: Dict[str, HealthAlert] = {}
        self._alert_counter = 0
        self._health_history: List[SystemHealth] = []
        self._max_history_size = 1000
        
        # Default thresholds
        self._default_thresholds = {
            ComponentType.CPU: {"warning": 80.0, "critical": 95.0},
            ComponentType.MEMORY: {"warning": 80.0, "critical": 95.0},
            ComponentType.DISK: {"warning": 85.0, "critical": 95.0},
            ComponentType.NETWORK: {"warning": 500.0, "critical": 1000.0},  # ms latency
            ComponentType.SERVICE: {"warning": 5000.0, "critical": 30000.0},  # ms response
        }
    
    def register_component(self, component_id: str, component_type: ComponentType,
                          name: str, initial_value: float = 0.0) -> str:
        """Register a component for monitoring."""
        thresholds = self._default_thresholds.get(component_type, {"warning": 80.0, "critical": 95.0})
        
        component = ComponentHealth(
            component_id=component_id,
            component_type=component_type,
            name=name,
            status=HealthStatus.UNKNOWN,
            value=initial_value,
            threshold_warning=thresholds["warning"],
            threshold_critical=thresholds["critical"],
        )
        
        self._components[component_id] = component
        return component_id
    
    def update_component_value(self, component_id: str, value: float) -> ComponentHealth:
        """Update component value and check health."""
        if component_id not in self._components:
            raise ValueError(f"Unknown component: {component_id}")
        
        component = self._components[component_id]
        component.value = value
        component.last_check = datetime.now(timezone.utc).isoformat()
        
        # Determine status
        if value >= component.threshold_critical:
            component.status = HealthStatus.CRITICAL
            component.message = f"Critical: {value}{component.unit} >= {component.threshold_critical}{component.unit}"
            self._create_alert(component, HealthStatus.CRITICAL)
        elif value >= component.threshold_warning:
            component.status = HealthStatus.WARNING
            component.message = f"Warning: {value}{component.unit} >= {component.threshold_warning}{component.unit}"
            self._create_alert(component, HealthStatus.WARNING)
        else:
            component.status = HealthStatus.HEALTHY
            component.message = ""
        
        return component
    
    def check_service_health(self, component_id: str, endpoint: str,
                            timeout_ms: int = 5000) -> ComponentHealth:
        """Check service health via endpoint."""
        # Simulated health check
        # In production, this would make HTTP request
        
        import random
        response_time = random.randint(50, 200)  # Simulated response time
        
        return self.update_component_value(component_id, float(response_time))
    
    def get_system_health(self) -> SystemHealth:
        """Get overall system health."""
        now = datetime.now(timezone.utc)
        
        if not self._components:
            return SystemHealth(
                timestamp=now.isoformat(),
                overall_status=HealthStatus.UNKNOWN,
                health_score=0.0,
                components={},
                warnings=[],
                critical_issues=[],
                recommendations=[],
            )
        
        # Calculate health score
        scores = []
        warnings = []
        critical_issues = []
        recommendations = []
        
        for component in self._components.values():
            if component.status == HealthStatus.CRITICAL:
                scores.append(0.0)
                critical_issues.append(f"{component.name}: {component.message}")
                recommendations.append(f"Investigate {component.name} immediately")
            elif component.status == HealthStatus.WARNING:
                scores.append(50.0)
                warnings.append(f"{component.name}: {component.message}")
                recommendations.append(f"Monitor {component.name} closely")
            elif component.status == HealthStatus.HEALTHY:
                scores.append(100.0)
            else:
                scores.append(0.0)
        
        health_score = sum(scores) / len(scores) if scores else 0.0
        
        # Determine overall status
        if critical_issues:
            overall_status = HealthStatus.CRITICAL
        elif warnings:
            overall_status = HealthStatus.WARNING
        elif health_score >= 80:
            overall_status = HealthStatus.HEALTHY
        elif health_score >= 50:
            overall_status = HealthStatus.DEGRADED
        else:
            overall_status = HealthStatus.CRITICAL
        
        health = SystemHealth(
            timestamp=now.isoformat(),
            overall_status=overall_status,
            health_score=health_score,
            components=dict(self._components),
            warnings=warnings,
            critical_issues=critical_issues,
            recommendations=recommendations,
        )
        
        # Store in history
        self._health_history.append(health)
        if len(self._health_history) > self._max_history_size:
            self._health_history = self._health_history[-self._max_history_size:]
        
        return health
    
    def get_component_health(self, component_id: str) -> Optional[Dict[str, Any]]:
        """Get health of specific component."""
        if component_id not in self._components:
            return None
        
        return self._components[component_id].to_dict()
    
    def get_all_components(self) -> List[Dict[str, Any]]:
        """Get all registered components."""
        return [c.to_dict() for c in self._components.values()]
    
    def get_alerts(self, unresolved_only: bool = True) -> List[Dict[str, Any]]:
        """Get health alerts."""
        alerts = list(self._alerts.values())
        
        if unresolved_only:
            alerts = [a for a in alerts if not a.acknowledged]
        
        # Sort by created_at (newest first)
        alerts.sort(key=lambda a: a.created_at, reverse=True)
        
        return [a.to_dict() for a in alerts]
    
    def acknowledge_alert(self, alert_id: str) -> bool:
        """Acknowledge an alert."""
        if alert_id not in self._alerts:
            return False
        
        self._alerts[alert_id].acknowledged = True
        self._alerts[alert_id].acknowledged_at = datetime.now(timezone.utc).isoformat()
        return True
    
    def get_health_trend(self, hours: int = 24) -> Dict[str, Any]:
        """Get health trend over time."""
        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=hours)
        
        history = [
            h for h in self._health_history
            if datetime.fromisoformat(h.timestamp) >= cutoff
        ]
        
        if not history:
            return {
                "period_hours": hours,
                "data_points": 0,
                "avg_health_score": 0.0,
                "min_health_score": 0.0,
                "max_health_score": 0.0,
                "trend": "unknown",
            }
        
        scores = [h.health_score for h in history]
        
        # Calculate trend (simple linear regression)
        if len(scores) >= 2:
            first_half_avg = sum(scores[:len(scores)//2]) / (len(scores)//2)
            second_half_avg = sum(scores[len(scores)//2:]) / (len(scores) - len(scores)//2)
            
            if second_half_avg > first_half_avg + 5:
                trend = "improving"
            elif second_half_avg < first_half_avg - 5:
                trend = "degrading"
            else:
                trend = "stable"
        else:
            trend = "stable"
        
        return {
            "period_hours": hours,
            "data_points": len(history),
            "avg_health_score": sum(scores) / len(scores),
            "min_health_score": min(scores),
            "max_health_score": max(scores),
            "trend": trend,
        }
    
    def _create_alert(self, component: ComponentHealth, severity: HealthStatus) -> None:
        """Create health alert."""
        self._alert_counter += 1
        
        alert = HealthAlert(
            alert_id=f"alert_{self._alert_counter}",
            component_id=component.component_id,
            severity=severity,
            title=f"{component.name} {severity.value}",
            message=component.message,
            value=component.value,
            threshold=component.threshold_critical if severity == HealthStatus.CRITICAL else component.threshold_warning,
        )
        
        self._alerts[alert.alert_id] = alert
    
    def get_health_summary(self) -> Dict[str, Any]:
        """Get health monitoring summary."""
        total_components = len(self._components)
        healthy_components = len([c for c in self._components.values() if c.status == HealthStatus.HEALTHY])
        warning_components = len([c for c in self._components.values() if c.status == HealthStatus.WARNING])
        critical_components = len([c for c in self._components.values() if c.status == HealthStatus.CRITICAL])
        
        total_alerts = len(self._alerts)
        unresolved_alerts = len([a for a in self._alerts.values() if not a.acknowledged])
        
        current_health = self.get_system_health()
        
        return {
            "total_components": total_components,
            "healthy_components": healthy_components,
            "warning_components": warning_components,
            "critical_components": critical_components,
            "total_alerts": total_alerts,
            "unresolved_alerts": unresolved_alerts,
            "current_health_score": current_health.health_score,
            "current_status": current_health.overall_status.value,
        }
    
    def set_thresholds(self, component_id: str, warning: float, critical: float) -> bool:
        """Set custom thresholds for a component."""
        if component_id not in self._components:
            return False
        
        component = self._components[component_id]
        component.threshold_warning = warning
        component.threshold_critical = critical
        
        # Re-evaluate status with new thresholds
        self.update_component_value(component_id, component.value)
        
        return True


def create_health_check_engine() -> HealthCheckEngine:
    """Factory function to create health check engine."""
    return HealthCheckEngine()
