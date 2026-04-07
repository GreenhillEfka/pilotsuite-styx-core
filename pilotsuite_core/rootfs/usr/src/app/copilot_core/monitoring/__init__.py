"""
Monitoring package for PilotSuite Styx Core.

Provides Prometheus-compatible metrics, health checks, and alerting.

Modules:
- metrics: Prometheus metrics collector and decorators
- health: Comprehensive health check service
- alerts: Alert rules and evaluation

Usage:
    from copilot_core.monitoring import (
        get_metrics_collector,
        get_health_checker,
        get_alert_evaluator,
    )
    
    # Record metrics
    metrics = get_metrics_collector()
    metrics.record_request("GET", "/api/v1/test", 200, 0.05)
    
    # Check health
    checker = get_health_checker()
    health = await checker.full_health_check()
    
    # Evaluate alerts
    evaluator = get_alert_evaluator()
    alerts = await evaluator.evaluate_all(cpu_percent=85, memory_percent=70)
"""

from copilot_core.monitoring.metrics import (
    get_metrics_collector,
    get_prometheus_metrics,
    track_request_latency,
    PrometheusMetrics,
)

from copilot_core.monitoring.health import (
    get_health_checker,
    HealthChecker,
)

from copilot_core.monitoring.alerts import (
    get_alert_evaluator,
    get_alert_rules_yaml,
    get_alert_rules_json,
    AlertEvaluator,
)

__all__ = [
    # Metrics
    "get_metrics_collector",
    "get_prometheus_metrics",
    "track_request_latency",
    "PrometheusMetrics",
    # Health
    "get_health_checker",
    "HealthChecker",
    # Alerts
    "get_alert_evaluator",
    "get_alert_rules_yaml",
    "get_alert_rules_json",
    "AlertEvaluator",
]
