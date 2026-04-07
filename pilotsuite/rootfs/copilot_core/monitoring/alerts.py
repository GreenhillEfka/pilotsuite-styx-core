"""
Alert Rules for Prometheus Monitoring

Defines alert rules and thresholds for:
- CPU usage
- Memory usage
- Disk usage
- Request latency
- Error rates
- Cache performance
- Connection pool health
- LLM API health
- Home Assistant integration

These rules can be used by:
- External Prometheus server configuration
- Internal alert evaluator
- Grafana alerting

Usage:
    from copilot_core.monitoring.alerts import get_alert_rules_yaml, AlertEvaluator
    
    # Get Prometheus YAML format
    yaml_config = get_alert_rules_yaml()
    
    # Or use internal evaluator
    evaluator = AlertEvaluator()
    alerts = await evaluator.evaluate_all()
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


# ============================================================================
# Prometheus Alert Rules (YAML format)
# ============================================================================

ALERT_RULES = [
    # System Resource Alerts
    {
        "alert": "HighCPUUsage",
        "expr": "system_cpu_usage_percent > 90",
        "for": "5m",
        "labels": {
            "severity": "critical",
            "category": "system",
        },
        "annotations": {
            "summary": "High CPU usage detected",
            "description": "CPU usage is above 90% (current value: {{ $value }}%) for more than 5 minutes.",
            "runbook_url": "https://runbooks.example.com/high-cpu",
        },
    },
    {
        "alert": "CriticalCPUUsage",
        "expr": "system_cpu_usage_percent > 95",
        "for": "2m",
        "labels": {
            "severity": "critical",
            "category": "system",
        },
        "annotations": {
            "summary": "Critical CPU usage detected",
            "description": "CPU usage is above 95% (current value: {{ $value }}%) for more than 2 minutes.",
            "runbook_url": "https://runbooks.example.com/critical-cpu",
        },
    },
    {
        "alert": "HighMemoryUsage",
        "expr": "system_memory_usage_percent > 85",
        "for": "5m",
        "labels": {
            "severity": "warning",
            "category": "system",
        },
        "annotations": {
            "summary": "High memory usage detected",
            "description": "Memory usage is above 85% (current value: {{ $value }}%) for more than 5 minutes.",
            "runbook_url": "https://runbooks.example.com/high-memory",
        },
    },
    {
        "alert": "CriticalMemoryUsage",
        "expr": "system_memory_usage_percent > 95",
        "for": "2m",
        "labels": {
            "severity": "critical",
            "category": "system",
        },
        "annotations": {
            "summary": "Critical memory usage detected",
            "description": "Memory usage is above 95% (current value: {{ $value }}%) for more than 2 minutes. OOM risk.",
            "runbook_url": "https://runbooks.example.com/critical-memory",
        },
    },
    {
        "alert": "HighDiskUsage",
        "expr": "system_disk_usage_percent > 80",
        "for": "10m",
        "labels": {
            "severity": "warning",
            "category": "system",
        },
        "annotations": {
            "summary": "High disk usage detected",
            "description": "Disk usage is above 80% (current value: {{ $value }}%) for more than 10 minutes.",
            "runbook_url": "https://runbooks.example.com/high-disk",
        },
    },
    {
        "alert": "CriticalDiskUsage",
        "expr": "system_disk_usage_percent > 95",
        "for": "5m",
        "labels": {
            "severity": "critical",
            "category": "system",
        },
        "annotations": {
            "summary": "Critical disk usage detected",
            "description": "Disk usage is above 95% (current value: {{ $value }}%) for more than 5 minutes.",
            "runbook_url": "https://runbooks.example.com/critical-disk",
        },
    },
    
    # HTTP Request Alerts
    {
        "alert": "HighRequestLatency",
        "expr": "histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m])) > 0.5",
        "for": "5m",
        "labels": {
            "severity": "warning",
            "category": "performance",
        },
        "annotations": {
            "summary": "High request latency detected",
            "description": "95th percentile request latency is above 500ms (current value: {{ $value }}s) for more than 5 minutes.",
            "runbook_url": "https://runbooks.example.com/high-latency",
        },
    },
    {
        "alert": "CriticalRequestLatency",
        "expr": "histogram_quantile(0.99, rate(http_request_duration_seconds_bucket[5m])) > 2.0",
        "for": "5m",
        "labels": {
            "severity": "critical",
            "category": "performance",
        },
        "annotations": {
            "summary": "Critical request latency detected",
            "description": "99th percentile request latency is above 2s (current value: {{ $value }}s) for more than 5 minutes.",
            "runbook_url": "https://runbooks.example.com/critical-latency",
        },
    },
    {
        "alert": "HighErrorRate",
        "expr": "sum(rate(http_requests_total{status=~\"5..\"}[5m])) / sum(rate(http_requests_total[5m])) > 0.05",
        "for": "5m",
        "labels": {
            "severity": "critical",
            "category": "errors",
        },
        "annotations": {
            "summary": "High HTTP error rate detected",
            "description": "HTTP 5xx error rate is above 5% (current value: {{ $value | humanizePercentage }}) for the last 5 minutes.",
            "runbook_url": "https://runbooks.example.com/high-error-rate",
        },
    },
    {
        "alert": "ElevatedErrorRate",
        "expr": "sum(rate(http_requests_total{status=~\"5..\"}[5m])) / sum(rate(http_requests_total[5m])) > 0.01",
        "for": "5m",
        "labels": {
            "severity": "warning",
            "category": "errors",
        },
        "annotations": {
            "summary": "Elevated HTTP error rate detected",
            "description": "HTTP 5xx error rate is above 1% (current value: {{ $value | humanizePercentage }}) for the last 5 minutes.",
            "runbook_url": "https://runbooks.example.com/elevated-error-rate",
        },
    },
    
    # Cache Performance Alerts
    {
        "alert": "LowCacheHitRatio",
        "expr": "cache_hit_ratio < 0.5",
        "for": "10m",
        "labels": {
            "severity": "warning",
            "category": "cache",
        },
        "annotations": {
            "summary": "Low cache hit ratio detected",
            "description": "Cache hit ratio is below 50% (current value: {{ $value | humanizePercentage }}) for more than 10 minutes.",
            "runbook_url": "https://runbooks.example.com/low-cache-hit",
        },
    },
    {
        "alert": "CriticalCacheHitRatio",
        "expr": "cache_hit_ratio < 0.2",
        "for": "10m",
        "labels": {
            "severity": "warning",
            "category": "cache",
        },
        "annotations": {
            "summary": "Critical cache hit ratio detected",
            "description": "Cache hit ratio is below 20% (current value: {{ $value | humanizePercentage }}) for more than 10 minutes. Cache may be ineffective.",
            "runbook_url": "https://runbooks.example.com/critical-cache-hit",
        },
    },
    
    # Connection Pool Alerts
    {
        "alert": "ConnectionPoolExhausted",
        "expr": "connection_pool_available == 0",
        "for": "2m",
        "labels": {
            "severity": "critical",
            "category": "connections",
        },
        "annotations": {
            "summary": "Connection pool exhausted",
            "description": "No connections available in pool {{ $labels.pool_name }} for more than 2 minutes.",
            "runbook_url": "https://runbooks.example.com/pool-exhausted",
        },
    },
    {
        "alert": "ConnectionPoolHighUtilization",
        "expr": "connection_pool_checked_out / connection_pool_size > 0.9",
        "for": "5m",
        "labels": {
            "severity": "warning",
            "category": "connections",
        },
        "annotations": {
            "summary": "Connection pool utilization high",
            "description": "Connection pool {{ $labels.pool_name }} utilization is above 90% (current value: {{ $value | humanizePercentage }}).",
            "runbook_url": "https://runbooks.example.com/pool-high-util",
        },
    },
    {
        "alert": "ConnectionPoolWaitTimeHigh",
        "expr": "histogram_quantile(0.95, rate(connection_pool_wait_seconds_bucket[5m])) > 0.1",
        "for": "5m",
        "labels": {
            "severity": "warning",
            "category": "connections",
        },
        "annotations": {
            "summary": "High connection pool wait time",
            "description": "95th percentile connection pool wait time is above 100ms (current value: {{ $value }}s).",
            "runbook_url": "https://runbooks.example.com/pool-wait-time",
        },
    },
    
    # LLM API Alerts
    {
        "alert": "LLMHighErrorRate",
        "expr": "sum(rate(llm_requests_total{status=~\"5..\"}[5m])) / sum(rate(llm_requests_total[5m])) > 0.1",
        "for": "5m",
        "labels": {
            "severity": "critical",
            "category": "llm",
        },
        "annotations": {
            "summary": "High LLM API error rate",
            "description": "LLM API error rate is above 10% for provider {{ $labels.provider }} (current value: {{ $value | humanizePercentage }}).",
            "runbook_url": "https://runbooks.example.com/llm-errors",
        },
    },
    {
        "alert": "LLMHighLatency",
        "expr": "histogram_quantile(0.95, rate(llm_request_duration_seconds_bucket[5m])) > 30",
        "for": "5m",
        "labels": {
            "severity": "warning",
            "category": "llm",
        },
        "annotations": {
            "summary": "High LLM API latency",
            "description": "95th percentile LLM API latency is above 30s for provider {{ $labels.provider }} (current value: {{ $value }}s).",
            "runbook_url": "https://runbooks.example.com/llm-latency",
        },
    },
    
    # Home Assistant Integration Alerts
    {
        "alert": "HomeAssistantUnavailable",
        "expr": "up{job=\"homeassistant\"} == 0",
        "for": "2m",
        "labels": {
            "severity": "critical",
            "category": "homeassistant",
        },
        "annotations": {
            "summary": "Home Assistant instance unavailable",
            "description": "Home Assistant instance has been unreachable for more than 2 minutes.",
            "runbook_url": "https://runbooks.example.com/ha-unavailable",
        },
    },
    {
        "alert": "HomeAssistantHighErrorRate",
        "expr": "sum(rate(homeassistant_requests_total{status=~\"5..\"}[5m])) / sum(rate(homeassistant_requests_total[5m])) > 0.1",
        "for": "5m",
        "labels": {
            "severity": "warning",
            "category": "homeassistant",
        },
        "annotations": {
            "summary": "High Home Assistant API error rate",
            "description": "Home Assistant API error rate is above 10% (current value: {{ $value | humanizePercentage }}).",
            "runbook_url": "https://runbooks.example.com/ha-errors",
        },
    },
    
    # Background Task Alerts
    {
        "alert": "BackgroundTaskFailure",
        "expr": "increase(background_task_duration_seconds_count{status=\"failure\"}[5m]) > 0",
        "for": "0m",
        "labels": {
            "severity": "warning",
            "category": "background-tasks",
        },
        "annotations": {
            "summary": "Background task failure detected",
            "description": "Background task {{ $labels.task_type }} has failed in the last 5 minutes.",
            "runbook_url": "https://runbooks.example.com/bg-task-failure",
        },
    },
    {
        "alert": "BackgroundTaskStuck",
        "expr": "background_tasks_running > 0 and histogram_quantile(0.95, rate(background_task_duration_seconds_bucket[30m])) > 300",
        "for": "30m",
        "labels": {
            "severity": "warning",
            "category": "background-tasks",
        },
        "annotations": {
            "summary": "Background task may be stuck",
            "description": "Background task {{ $labels.task_type }} has been running for more than 5 minutes (95th percentile).",
            "runbook_url": "https://runbooks.example.com/bg-task-stuck",
        },
    },
]


def get_alert_rules_yaml() -> str:
    """
    Generate Prometheus alert rules in YAML format.
    
    Returns:
        str: YAML-formatted alert rules configuration
    """
    try:
        import yaml
    except ImportError:
        logger.warning("PyYAML not installed, returning JSON-like string")
        return str({"groups": [{"name": "copilot-core-alerts", "rules": ALERT_RULES}]})
    
    config = {
        "groups": [
            {
                "name": "copilot-core-alerts",
                "rules": ALERT_RULES,
            }
        ]
    }
    
    return yaml.dump(config, default_flow_style=False, sort_keys=False)


def get_alert_rules_json() -> List[Dict[str, Any]]:
    """
    Get alert rules as JSON-serializable list.
    
    Returns:
        list: Alert rules as dictionaries
    """
    return ALERT_RULES


# ============================================================================
# Internal Alert Evaluator
# ============================================================================


@dataclass
class AlertState:
    """Current state of an alert."""
    
    name: str
    severity: str
    category: str
    is_firing: bool = False
    start_time: Optional[float] = None
    last_evaluated: Optional[float] = None
    current_value: Optional[float] = None
    threshold: Optional[float] = None
    annotations: Dict[str, str] = field(default_factory=dict)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "name": self.name,
            "severity": self.severity,
            "category": self.category,
            "is_firing": self.is_firing,
            "start_time": self.start_time,
            "duration_seconds": (time.time() - self.start_time) if self.start_time else 0,
            "current_value": self.current_value,
            "threshold": self.threshold,
            "annotations": self.annotations,
        }


class AlertEvaluator:
    """
    Internal alert rule evaluator.
    
    Evaluates alert rules against current metrics and tracks alert state.
    Used when Prometheus server is not available.
    """
    
    def __init__(self):
        self._alert_states: Dict[str, AlertState] = {}
        self._thresholds = {
            "cpu_warning": 80,
            "cpu_critical": 95,
            "memory_warning": 85,
            "memory_critical": 95,
            "disk_warning": 80,
            "disk_critical": 95,
            "latency_warning": 0.5,  # 500ms
            "latency_critical": 2.0,  # 2s
            "error_rate_warning": 0.01,  # 1%
            "error_rate_critical": 0.05,  # 5%
            "cache_hit_warning": 0.5,  # 50%
            "cache_hit_critical": 0.2,  # 20%
        }
    
    async def evaluate_system_metrics(
        self,
        cpu_percent: float,
        memory_percent: float,
        disk_percent: float,
    ) -> List[AlertState]:
        """Evaluate system resource alerts."""
        alerts = []
        
        # CPU alerts
        if cpu_percent > self._thresholds["cpu_critical"]:
            alerts.append(self._create_alert(
                "HighCPUUsage", "critical", "system",
                f"CPU usage critical: {cpu_percent}%",
                cpu_percent, self._thresholds["cpu_critical"],
            ))
        elif cpu_percent > self._thresholds["cpu_warning"]:
            alerts.append(self._create_alert(
                "HighCPUUsage", "warning", "system",
                f"CPU usage high: {cpu_percent}%",
                cpu_percent, self._thresholds["cpu_warning"],
            ))
        
        # Memory alerts
        if memory_percent > self._thresholds["memory_critical"]:
            alerts.append(self._create_alert(
                "HighMemoryUsage", "critical", "system",
                f"Memory usage critical: {memory_percent}%",
                memory_percent, self._thresholds["memory_critical"],
            ))
        elif memory_percent > self._thresholds["memory_warning"]:
            alerts.append(self._create_alert(
                "HighMemoryUsage", "warning", "system",
                f"Memory usage high: {memory_percent}%",
                memory_percent, self._thresholds["memory_warning"],
            ))
        
        # Disk alerts
        if disk_percent > self._thresholds["disk_critical"]:
            alerts.append(self._create_alert(
                "HighDiskUsage", "critical", "system",
                f"Disk usage critical: {disk_percent}%",
                disk_percent, self._thresholds["disk_critical"],
            ))
        elif disk_percent > self._thresholds["disk_warning"]:
            alerts.append(self._create_alert(
                "HighDiskUsage", "warning", "system",
                f"Disk usage high: {disk_percent}%",
                disk_percent, self._thresholds["disk_warning"],
            ))
        
        return alerts
    
    async def evaluate_http_metrics(
        self,
        error_rate: float,
        latency_p95: float,
        latency_p99: float,
    ) -> List[AlertState]:
        """Evaluate HTTP request alerts."""
        alerts = []
        
        # Error rate alerts
        if error_rate > self._thresholds["error_rate_critical"]:
            alerts.append(self._create_alert(
                "HighErrorRate", "critical", "errors",
                f"HTTP 5xx error rate critical: {error_rate:.2%}",
                error_rate, self._thresholds["error_rate_critical"],
            ))
        elif error_rate > self._thresholds["error_rate_warning"]:
            alerts.append(self._create_alert(
                "HighErrorRate", "warning", "errors",
                f"HTTP 5xx error rate elevated: {error_rate:.2%}",
                error_rate, self._thresholds["error_rate_warning"],
            ))
        
        # Latency alerts
        if latency_p99 > self._thresholds["latency_critical"]:
            alerts.append(self._create_alert(
                "CriticalRequestLatency", "critical", "performance",
                f"P99 latency critical: {latency_p99:.2f}s",
                latency_p99, self._thresholds["latency_critical"],
            ))
        elif latency_p95 > self._thresholds["latency_warning"]:
            alerts.append(self._create_alert(
                "HighRequestLatency", "warning", "performance",
                f"P95 latency high: {latency_p95:.2f}s",
                latency_p95, self._thresholds["latency_warning"],
            ))
        
        return alerts
    
    async def evaluate_cache_metrics(
        self,
        hit_ratio: float,
    ) -> List[AlertState]:
        """Evaluate cache performance alerts."""
        alerts = []
        
        if hit_ratio < self._thresholds["cache_hit_critical"]:
            alerts.append(self._create_alert(
                "CriticalCacheHitRatio", "warning", "cache",
                f"Cache hit ratio critical: {hit_ratio:.2%}",
                hit_ratio, self._thresholds["cache_hit_critical"],
                invert=True,  # Lower is worse
            ))
        elif hit_ratio < self._thresholds["cache_hit_warning"]:
            alerts.append(self._create_alert(
                "LowCacheHitRatio", "warning", "cache",
                f"Cache hit ratio low: {hit_ratio:.2%}",
                hit_ratio, self._thresholds["cache_hit_warning"],
                invert=True,
            ))
        
        return alerts
    
    def _create_alert(
        self,
        name: str,
        severity: str,
        category: str,
        description: str,
        current_value: float,
        threshold: float,
        invert: bool = False,
    ) -> AlertState:
        """Create or update an alert state."""
        is_firing = (current_value > threshold and not invert) or (current_value < threshold and invert)
        
        if name not in self._alert_states:
            self._alert_states[name] = AlertState(
                name=name,
                severity=severity,
                category=category,
                annotations={"description": description},
            )
        
        state = self._alert_states[name]
        state.is_firing = is_firing
        state.current_value = current_value
        state.threshold = threshold
        state.last_evaluated = time.time()
        state.annotations["description"] = description
        
        if is_firing and state.start_time is None:
            state.start_time = time.time()
        elif not is_firing:
            state.start_time = None
        
        return state
    
    async def evaluate_all(
        self,
        cpu_percent: float = 0,
        memory_percent: float = 0,
        disk_percent: float = 0,
        error_rate: float = 0,
        latency_p95: float = 0,
        latency_p99: float = 0,
        cache_hit_ratio: float = 1.0,
    ) -> Dict[str, Any]:
        """
        Evaluate all alert rules.
        
        Args:
            cpu_percent: Current CPU usage percentage
            memory_percent: Current memory usage percentage
            disk_percent: Current disk usage percentage
            error_rate: HTTP 5xx error rate (0.0 to 1.0)
            latency_p95: 95th percentile request latency in seconds
            latency_p99: 99th percentile request latency in seconds
            cache_hit_ratio: Cache hit ratio (0.0 to 1.0)
        
        Returns:
            dict: Evaluation results with firing alerts
        """
        all_alerts = []
        
        # Evaluate each category
        all_alerts.extend(await self.evaluate_system_metrics(
            cpu_percent, memory_percent, disk_percent
        ))
        all_alerts.extend(await self.evaluate_http_metrics(
            error_rate, latency_p95, latency_p99
        ))
        all_alerts.extend(await self.evaluate_cache_metrics(
            cache_hit_ratio
        ))
        
        # Get firing alerts
        firing_alerts = [a for a in all_alerts if a.is_firing]
        
        # Determine overall status
        if any(a.severity == "critical" for a in firing_alerts):
            status = "critical"
        elif firing_alerts:
            status = "warning"
        else:
            status = "healthy"
        
        return {
            "status": status,
            "timestamp": time.time(),
            "firing_count": len(firing_alerts),
            "firing_alerts": [a.to_dict() for a in firing_alerts],
            "all_alerts": [a.to_dict() for a in all_alerts],
        }


# Global evaluator instance
_evaluator: Optional[AlertEvaluator] = None


def get_alert_evaluator() -> AlertEvaluator:
    """Get or create the global alert evaluator."""
    global _evaluator
    if _evaluator is None:
        _evaluator = AlertEvaluator()
    return _evaluator
