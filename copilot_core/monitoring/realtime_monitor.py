"""Real-Time Monitoring — Metrics, Alerts, Dashboards, Anomaly Detection."""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional
from collections import deque
from enum import Enum

logger = logging.getLogger(__name__)


class AlertSeverity(Enum):
    """Alert severity levels."""
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class MetricPoint:
    """Single metric data point."""
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class Alert:
    """Monitoring alert."""
    id: str
    name: str
    severity: AlertSeverity
    message: str
    triggered_at: float
    resolved_at: Optional[float] = None
    metric_name: str = ""
    threshold: float = 0.0
    current_value: float = 0.0


@dataclass
class Dashboard:
    """Monitoring dashboard."""
    id: str
    name: str
    panels: List[Dict] = field(default_factory=list)
    refresh_interval_seconds: int = 30


class RealTimeMonitor:
    """Real-time monitoring and alerting system."""

    def __init__(self, retention_points: int = 1000):
        self._metrics: Dict[str, deque] = {}
        self._alerts: Dict[str, Alert] = {}
        self._alert_handlers: List[Callable] = []
        self._dashboards: Dict[str, Dashboard] = {}
        self._retention_points = retention_points
        self._thresholds: Dict[str, Dict] = {}

    def record_metric(self, name: str, value: float, labels: Optional[Dict] = None):
        """Record a metric data point."""
        if name not in self._metrics:
            self._metrics[name] = deque(maxlen=self._retention_points)
        
        point = MetricPoint(
            timestamp=time.time(),
            value=value,
            labels=labels or {}
        )
        self._metrics[name].append(point)
        
        # Check thresholds
        self._check_thresholds(name, value)

    def _check_thresholds(self, metric_name: str, value: float):
        """Check if metric exceeds thresholds."""
        if metric_name not in self._thresholds:
            return
        
        thresholds = self._thresholds[metric_name]
        
        if "critical" in thresholds and value >= thresholds["critical"]:
            self._trigger_alert(metric_name, value, AlertSeverity.CRITICAL, thresholds["critical"])
        elif "warning" in thresholds and value >= thresholds["warning"]:
            self._trigger_alert(metric_name, value, AlertSeverity.WARNING, thresholds["warning"])

    def _trigger_alert(self, metric_name: str, value: float, severity: AlertSeverity, threshold: float):
        """Trigger an alert."""
        alert_id = f"{metric_name}_{severity.value}"
        
        # Check if alert already active
        if alert_id in self._alerts and not self._alerts[alert_id].resolved_at:
            return
        
        alert = Alert(
            id=alert_id,
            name=f"{metric_name} {severity.value}",
            severity=severity,
            message=f"{metric_name} is {value:.2f} (threshold: {threshold:.2f})",
            triggered_at=time.time(),
            metric_name=metric_name,
            threshold=threshold,
            current_value=value,
        )
        
        self._alerts[alert_id] = alert
        logger.warning(f"Alert triggered: {alert.name}")
        
        # Notify handlers
        for handler in self._alert_handlers:
            try:
                handler(alert)
            except Exception as e:
                logger.error(f"Alert handler failed: {e}")

    def set_threshold(self, metric_name: str, warning: Optional[float] = None, critical: Optional[float] = None):
        """Set thresholds for a metric."""
        self._thresholds[metric_name] = {}
        if warning is not None:
            self._thresholds[metric_name]["warning"] = warning
        if critical is not None:
            self._thresholds[metric_name]["critical"] = critical
        
        logger.info(f"Thresholds set for {metric_name}: warning={warning}, critical={critical}")

    def resolve_alert(self, alert_id: str):
        """Resolve an alert."""
        if alert_id in self._alerts:
            self._alerts[alert_id].resolved_at = time.time()
            logger.info(f"Alert resolved: {alert_id}")

    def get_metric_stats(self, metric_name: str, window_seconds: int = 300) -> Dict[str, Any]:
        """Get statistics for a metric."""
        if metric_name not in self._metrics:
            return {"error": "Metric not found"}
        
        points = list(self._metrics[metric_name])
        cutoff = time.time() - window_seconds
        recent = [p for p in points if p.timestamp >= cutoff]
        
        if not recent:
            return {"count": 0}
        
        values = [p.value for p in recent]
        
        return {
            "count": len(values),
            "min": min(values),
            "max": max(values),
            "avg": sum(values) / len(values),
            "current": values[-1] if values else 0,
            "window_seconds": window_seconds,
        }

    def get_active_alerts(self) -> List[Alert]:
        """Get all active (unresolved) alerts."""
        return [a for a in self._alerts.values() if not a.resolved_at]

    def get_alert_history(self, limit: int = 50) -> List[Alert]:
        """Get alert history."""
        sorted_alerts = sorted(
            self._alerts.values(),
            key=lambda a: a.triggered_at,
            reverse=True
        )
        return sorted_alerts[:limit]

    def register_alert_handler(self, handler: Callable):
        """Register an alert notification handler."""
        self._alert_handlers.append(handler)

    def create_dashboard(self, dashboard: Dashboard) -> str:
        """Create a monitoring dashboard."""
        self._dashboards[dashboard.id] = dashboard
        logger.info(f"Dashboard created: {dashboard.name}")
        return dashboard.id

    def create_system_dashboard(self) -> Dashboard:
        """Create default system monitoring dashboard."""
        dashboard = Dashboard(
            id="system_overview",
            name="System Overview",
            panels=[
                {
                    "id": "cpu_usage",
                    "title": "CPU Usage",
                    "type": "gauge",
                    "metric": "system.cpu.percent",
                    "thresholds": {"warning": 70, "critical": 90},
                },
                {
                    "id": "memory_usage",
                    "title": "Memory Usage",
                    "type": "gauge",
                    "metric": "system.memory.percent",
                    "thresholds": {"warning": 80, "critical": 95},
                },
                {
                    "id": "api_latency",
                    "title": "API Latency (p99)",
                    "type": "timeseries",
                    "metric": "api.latency.p99",
                    "thresholds": {"warning": 200, "critical": 500},
                },
                {
                    "id": "request_rate",
                    "title": "Request Rate",
                    "type": "timeseries",
                    "metric": "api.requests.per_second",
                },
                {
                    "id": "error_rate",
                    "title": "Error Rate",
                    "type": "stat",
                    "metric": "api.errors.per_second",
                    "thresholds": {"warning": 1, "critical": 10},
                },
                {
                    "id": "active_alerts",
                    "title": "Active Alerts",
                    "type": "alert_list",
                },
            ],
            refresh_interval_seconds=30,
        )
        
        return self.create_dashboard(dashboard)

    def get_dashboard_data(self, dashboard_id: str) -> Optional[Dict]:
        """Get dashboard data."""
        if dashboard_id not in self._dashboards:
            return None
        
        dashboard = self._dashboards[dashboard_id]
        data = {
            "id": dashboard.id,
            "name": dashboard.name,
            "panels": [],
        }
        
        for panel in dashboard.panels:
            metric = panel.get("metric")
            if metric and metric in self._metrics:
                stats = self.get_metric_stats(metric)
                data["panels"].append({
                    "id": panel["id"],
                    "title": panel["title"],
                    "type": panel["type"],
                    "data": stats,
                })
            elif panel.get("type") == "alert_list":
                data["panels"].append({
                    "id": panel["id"],
                    "title": panel["title"],
                    "type": panel["type"],
                    "data": {"alerts": [a.__dict__ for a in self.get_active_alerts()]},
                })
        
        return data

    def export_prometheus_format(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []
        
        for metric_name, points in self._metrics.items():
            if not points:
                continue
            
            latest = points[-1]
            labels_str = ",".join(f'{k}="{v}"' for k, v in latest.labels.items())
            if labels_str:
                lines.append(f'{metric_name}{{{labels_str}}} {latest.value}')
            else:
                lines.append(f"{metric_name} {latest.value}")
        
        return "\n".join(lines)

    def get_stats(self) -> Dict[str, Any]:
        """Get monitoring statistics."""
        return {
            "metrics_tracked": len(self._metrics),
            "active_alerts": len(self.get_active_alerts()),
            "total_alerts": len(self._alerts),
            "dashboards": len(self._dashboards),
        }


# Global default real-time monitor
default_monitor: Optional[RealTimeMonitor] = None


def init_realtime_monitor(retention_points: int = 1000) -> RealTimeMonitor:
    """Initialize global real-time monitor."""
    global default_monitor
    default_monitor = RealTimeMonitor(retention_points)
    return default_monitor
