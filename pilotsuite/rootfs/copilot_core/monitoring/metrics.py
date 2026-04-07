"""
Prometheus Metrics Collector for PilotSuite Styx Core

Provides Prometheus-compatible metrics for:
- HTTP request latency histograms
- Error rate counters
- Cache hit/miss gauges
- Connection pool metrics
- System resource usage (CPU, Memory)

Usage:
    from copilot_core.monitoring.metrics import (
        PrometheusMetrics, 
        track_request_latency,
        record_cache_hit,
        record_cache_miss
    )
    
    metrics = PrometheusMetrics()
    
    # In Flask middleware or route:
    @track_request_latency
    def my_route():
        ...
"""

from __future__ import annotations

import logging
import os
import time
import psutil
from functools import wraps
from typing import Any, Dict, Optional, Tuple

from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    REGISTRY,
)

logger = logging.getLogger(__name__)

# --- Metric Definitions ---

# Request Metrics
REQUEST_LATENCY = Histogram(
    "http_request_duration_seconds",
    "HTTP request latency in seconds",
    ["method", "endpoint", "status"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0),
)

REQUEST_COUNT = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status"],
)

REQUESTS_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "Number of HTTP requests currently being processed",
    ["method", "endpoint"],
)

# Application Info
APP_INFO = Gauge(
    "app_info",
    "Application information",
    ["version", "environment", "python_version"],
)

# System Metrics
SYSTEM_CPU_USAGE = Gauge(
    "system_cpu_usage_percent",
    "System CPU usage in percent"
)

SYSTEM_MEMORY_USAGE_BYTES = Gauge(
    "system_memory_usage_bytes",
    "System memory usage in bytes"
)

SYSTEM_MEMORY_USAGE_PERCENT = Gauge(
    "system_memory_usage_percent",
    "System memory usage in percent"
)

SYSTEM_DISK_USAGE_PERCENT = Gauge(
    "system_disk_usage_percent",
    "System disk usage in percent"
)

# Cache Metrics
CACHE_HITS = Counter(
    "cache_hits_total",
    "Total number of cache hits",
    ["cache_name"],
)

CACHE_MISSES = Counter(
    "cache_misses_total",
    "Total number of cache misses",
    ["cache_name"],
)

CACHE_SIZE = Gauge(
    "cache_size_entries",
    "Current number of entries in cache",
    ["cache_name"],
)

CACHE_HIT_RATIO = Gauge(
    "cache_hit_ratio",
    "Cache hit ratio (0.0 to 1.0)",
    ["cache_name"],
)

# Connection Pool Metrics
CONNECTION_POOL_SIZE = Gauge(
    "connection_pool_size",
    "Current size of the connection pool",
    ["pool_name"],
)

CONNECTION_POOL_CHECKED_OUT = Gauge(
    "connection_pool_checked_out",
    "Number of connections currently checked out",
    ["pool_name"],
)

CONNECTION_POOL_AVAILABLE = Gauge(
    "connection_pool_available",
    "Number of connections available in pool",
    ["pool_name"],
)

CONNECTION_POOL_WAIT_TIME = Histogram(
    "connection_pool_wait_seconds",
    "Time spent waiting for connection from pool",
    ["pool_name"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)

# LLM/Model Metrics
LLM_REQUEST_COUNT = Counter(
    "llm_requests_total",
    "Total number of LLM API requests",
    ["provider", "model", "status"],
)

LLM_TOKEN_USAGE = Counter(
    "llm_tokens_total",
    "Total number of tokens used",
    ["provider", "model", "type"],  # type: prompt or completion
)

LLM_LATENCY = Histogram(
    "llm_request_duration_seconds",
    "LLM API request latency in seconds",
    ["provider", "model", "status"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, 60.0),
)

# Home Assistant Integration Metrics
HA_REQUEST_COUNT = Counter(
    "homeassistant_requests_total",
    "Total number of Home Assistant API requests",
    ["endpoint", "status"],
)

HA_WEBSOCKET_CONNECTIONS = Gauge(
    "homeassistant_websocket_connections",
    "Number of active WebSocket connections to Home Assistant"
)

# Background Task Metrics
BACKGROUND_TASK_COUNT = Gauge(
    "background_tasks_running",
    "Number of background tasks currently running",
    ["task_type"],
)

BACKGROUND_TASK_DURATION = Histogram(
    "background_task_duration_seconds",
    "Background task execution duration",
    ["task_type", "status"],  # status: success, failure
    buckets=(0.1, 0.5, 1.0, 5.0, 10.0, 30.0, 60.0, 300.0),
)


class PrometheusMetrics:
    """
    Central metrics collector and manager.
    
    Provides methods to record various metrics and generate
    Prometheus-formatted output.
    """
    
    _instance: Optional["PrometheusMetrics"] = None
    
    def __init__(self, app_version: str = "0.0.0", environment: str = "production"):
        self.app_version = app_version
        self.environment = environment
        self._initialized = False
        
        # Initialize app info metric
        import sys
        APP_INFO.labels(
            version=app_version,
            environment=environment,
            python_version=sys.version.split()[0]
        ).set(1)
    
    @classmethod
    def get_instance(cls, app_version: str = "0.0.0", environment: str = "production") -> "PrometheusMetrics":
        """Get or create singleton instance."""
        if cls._instance is None:
            cls._instance = cls(app_version=app_version, environment=environment)
        return cls._instance
    
    def record_request(self, method: str, endpoint: str, status: int, duration: float) -> None:
        """Record HTTP request metrics."""
        status_str = str(status)
        REQUEST_LATENCY.labels(method=method, endpoint=endpoint, status=status_str).observe(duration)
        REQUEST_COUNT.labels(method=method, endpoint=endpoint, status=status_str).inc()
    
    def start_request(self, method: str, endpoint: str) -> float:
        """Mark request start for timing."""
        REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).inc()
        return time.time()
    
    def end_request(self, method: str, endpoint: str, status: int, start_time: float) -> None:
        """Mark request end and record metrics."""
        REQUESTS_IN_PROGRESS.labels(method=method, endpoint=endpoint).dec()
        duration = time.time() - start_time
        self.record_request(method, endpoint, status, duration)
    
    def record_cache_hit(self, cache_name: str = "default") -> None:
        """Record a cache hit."""
        CACHE_HITS.labels(cache_name=cache_name).inc()
        self._update_cache_ratio(cache_name)
    
    def record_cache_miss(self, cache_name: str = "default") -> None:
        """Record a cache miss."""
        CACHE_MISSES.labels(cache_name=cache_name).inc()
        self._update_cache_ratio(cache_name)
    
    def set_cache_size(self, size: int, cache_name: str = "default") -> None:
        """Set current cache size."""
        CACHE_SIZE.labels(cache_name=cache_name).set(size)
        self._update_cache_ratio(cache_name)
    
    def _update_cache_ratio(self, cache_name: str = "default") -> None:
        """Update cache hit ratio gauge."""
        # Get metrics from registry
        hits = 0
        misses = 0
        for sample in CACHE_HITS.collect():
            for s in sample.samples:
                if s.labels.get("cache_name") == cache_name:
                    hits = int(s.value)
                    break
        
        for sample in CACHE_MISSES.collect():
            for s in sample.samples:
                if s.labels.get("cache_name") == cache_name:
                    misses = int(s.value)
                    break
        
        total = hits + misses
        if total > 0:
            CACHE_HIT_RATIO.labels(cache_name=cache_name).set(hits / total)
    
    def set_connection_pool_metrics(
        self,
        pool_name: str,
        size: int,
        checked_out: int,
        available: int,
    ) -> None:
        """Update connection pool metrics."""
        CONNECTION_POOL_SIZE.labels(pool_name=pool_name).set(size)
        CONNECTION_POOL_CHECKED_OUT.labels(pool_name=pool_name).set(checked_out)
        CONNECTION_POOL_AVAILABLE.labels(pool_name=pool_name).set(available)
    
    def record_connection_wait(self, pool_name: str, wait_time: float) -> None:
        """Record time spent waiting for connection."""
        CONNECTION_POOL_WAIT_TIME.labels(pool_name=pool_name).observe(wait_time)
    
    def record_llm_request(
        self,
        provider: str,
        model: str,
        status: int,
        duration: float,
        prompt_tokens: int = 0,
        completion_tokens: int = 0,
    ) -> None:
        """Record LLM API request metrics."""
        status_str = str(status)
        LLM_REQUEST_COUNT.labels(provider=provider, model=model, status=status_str).inc()
        LLM_LATENCY.labels(provider=provider, model=model, status=status_str).observe(duration)
        
        if prompt_tokens > 0:
            LLM_TOKEN_USAGE.labels(provider=provider, model=model, type="prompt").inc(prompt_tokens)
        if completion_tokens > 0:
            LLM_TOKEN_USAGE.labels(provider=provider, model=model, type="completion").inc(completion_tokens)
    
    def record_ha_request(self, endpoint: str, status: int) -> None:
        """Record Home Assistant API request."""
        status_str = str(status)
        HA_REQUEST_COUNT.labels(endpoint=endpoint, status=status_str).inc()
    
    def set_ha_websocket_connections(self, count: int) -> None:
        """Set active HA WebSocket connection count."""
        HA_WEBSOCKET_CONNECTIONS.set(count)
    
    def start_background_task(self, task_type: str) -> None:
        """Mark background task start."""
        BACKGROUND_TASK_COUNT.labels(task_type=task_type).inc()
    
    def end_background_task(self, task_type: str, status: str, duration: float) -> None:
        """Mark background task end and record metrics."""
        BACKGROUND_TASK_COUNT.labels(task_type=task_type).dec()
        BACKGROUND_TASK_DURATION.labels(task_type=task_type, status=status).observe(duration)
    
    def update_system_metrics(self) -> None:
        """Update system-level metrics (CPU, Memory, Disk)."""
        SYSTEM_CPU_USAGE.set(psutil.cpu_percent(interval=0.1))
        memory = psutil.virtual_memory()
        SYSTEM_MEMORY_USAGE_BYTES.set(memory.used)
        SYSTEM_MEMORY_USAGE_PERCENT.set(memory.percent)
        
        disk = psutil.disk_usage("/")
        SYSTEM_DISK_USAGE_PERCENT.set(disk.percent)
    
    def get_metrics(self) -> Tuple[bytes, str]:
        """
        Generate Prometheus-formatted metrics.
        
        Returns:
            Tuple of (metrics_bytes, content_type)
        """
        self.update_system_metrics()
        return generate_latest(REGISTRY), CONTENT_TYPE_LATEST


def track_request_latency(func):
    """
    Decorator to track latency of a function.
    
    Usage:
        @track_request_latency
        def my_endpoint():
            ...
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        start_time = time.time()
        endpoint = func.__name__
        method = "UNKNOWN"
        
        # Try to extract method from request if available
        try:
            from flask import request
            method = request.method
            endpoint = request.endpoint or endpoint
        except Exception:
            pass
        
        status = 200
        try:
            response = func(*args, **kwargs)
            if hasattr(response, "status_code"):
                status = response.status_code
            return response
        except Exception as e:
            status = 500
            logger.warning(f"Request failed in {endpoint}: {e}")
            raise
        finally:
            duration = time.time() - start_time
            metrics = PrometheusMetrics.get_instance()
            metrics.record_request(method, endpoint, status, duration)
    
    return wrapper


# Global instance
_metrics_instance: Optional[PrometheusMetrics] = None


def get_metrics_collector(app_version: str = "0.0.0", environment: str = "production") -> PrometheusMetrics:
    """Get or create the global metrics collector."""
    global _metrics_instance
    if _metrics_instance is None:
        _metrics_instance = PrometheusMetrics(app_version=app_version, environment=environment)
    return _metrics_instance


def get_prometheus_metrics() -> Tuple[bytes, str]:
    """Get Prometheus-formatted metrics (compatibility wrapper)."""
    return get_metrics_collector().get_metrics()
