"""
Metrics API Blueprint for Prometheus

Provides Flask endpoints for:
- /metrics - Prometheus metrics endpoint
- /health - Extended health check endpoint
- /ready - Readiness probe

Usage:
    from copilot_core.api.v1.metrics import metrics_bp
    app.register_blueprint(metrics_bp)
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Dict, Optional

from flask import Blueprint, Response, jsonify, request

try:
    from copilot_core.monitoring.metrics import get_prometheus_metrics, get_metrics_collector
except Exception as exc:  # pragma: no cover - depends on optional runtime deps
    get_prometheus_metrics = None  # type: ignore[assignment]
    get_metrics_collector = None  # type: ignore[assignment]
    _METRICS_IMPORT_ERROR: Optional[Exception] = exc
else:
    _METRICS_IMPORT_ERROR = None

try:
    from copilot_core.monitoring.health import get_health_checker
except Exception as exc:  # pragma: no cover - depends on optional runtime deps
    get_health_checker = None  # type: ignore[assignment]
    _HEALTH_IMPORT_ERROR: Optional[Exception] = exc
else:
    _HEALTH_IMPORT_ERROR = None

logger = logging.getLogger(__name__)

# Create blueprint with relative prefix (will be nested under /api/v1)
metrics_bp = Blueprint("metrics", __name__)


def _metrics_unavailable_response():
    return jsonify({
        "error": "metrics_unavailable",
        "message": "Optional monitoring dependencies are not installed",
    }), 503


def _health_checker_unavailable_response(status_code: int):
    return jsonify({
        "status": "degraded" if status_code == 200 else "unhealthy",
        "error": "health_checker_unavailable",
        "message": "Optional monitoring dependencies are not installed",
    }), status_code


def _run_async(coro, timeout: int = 10):
    """Run async coroutine from sync Flask context.

    Re-uses the current event loop if one is running (e.g. inside
    an existing async application), otherwise creates a temporary one.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, asyncio.wait_for(coro, timeout=timeout))
            return future.result(timeout=timeout + 2)

    return asyncio.run(asyncio.wait_for(coro, timeout=timeout))


@metrics_bp.route("/metrics", methods=["GET"])
def prometheus_metrics():
    """
    Prometheus metrics endpoint.
    
    Returns metrics in Prometheus text exposition format.
    Content-Type: text/plain; version=0.0.4; charset=utf-8
    
    Metrics include:
    - HTTP request latency histograms
    - Error rate counters
    - Cache hit/miss gauges
    - Connection pool metrics
    - System CPU/Memory/Disk usage
    - LLM API metrics
    - Home Assistant integration metrics
    """
    if get_prometheus_metrics is None:
        if _METRICS_IMPORT_ERROR is not None:
            logger.info("Prometheus metrics unavailable: %s", _METRICS_IMPORT_ERROR)
        return _metrics_unavailable_response()

    try:
        data, content_type = get_prometheus_metrics()
        return Response(data, mimetype=content_type)
    except Exception as e:
        logger.error(f"Failed to generate Prometheus metrics: {e}")
        return jsonify({
            "error": "metrics_generation_failed",
            "message": str(e),
        }), 500


@metrics_bp.route("/health", methods=["GET"])
def health_check():
    """
    Extended health check endpoint.
    
    Query params:
    - full: If "true", run complete health check (including external services)
    - timeout: Maximum time to wait for health check (default: 10s)
    
    Returns comprehensive health status including:
    - System resources (CPU, Memory, Disk)
    - Python dependencies
    - Internal modules
    - Storage paths
    - External services (Home Assistant, Ollama, etc.)
    """
    if get_health_checker is None:
        if _HEALTH_IMPORT_ERROR is not None:
            logger.info("Health checker unavailable: %s", _HEALTH_IMPORT_ERROR)
        return _health_checker_unavailable_response(200)

    try:
        full_check = request.args.get("full", "false").lower() == "true"
        timeout = int(request.args.get("timeout", "10"))

        checker = get_health_checker()

        if full_check:
            health = _run_async(checker.full_health_check(), timeout=timeout)
        else:
            health = _run_async(checker.get_quick_health(), timeout=timeout)
        
        status_code = 200
        if health.get("status") == "unhealthy":
            status_code = 503
        elif health.get("status") == "degraded":
            status_code = 200  # Still serve, but degraded
        
        return jsonify(health), status_code
        
    except asyncio.TimeoutError:
        logger.warning("Health check timed out")
        return jsonify({
            "status": "degraded",
            "error": "health_check_timeout",
            "message": f"Health check exceeded {timeout}s timeout",
        }), 200
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return jsonify({
            "status": "unhealthy",
            "error": "health_check_failed",
            "message": str(e),
        }), 500


@metrics_bp.route("/ready", methods=["GET"])
def readiness_probe():
    """
    Readiness probe endpoint.
    
    Checks if the application is ready to serve traffic.
    Simpler than /health - only checks critical dependencies.
    
    Returns:
    - 200: Ready to serve
    - 503: Not ready (still initializing or critical failure)
    """
    if get_health_checker is None:
        if _HEALTH_IMPORT_ERROR is not None:
            logger.info("Readiness probe unavailable: %s", _HEALTH_IMPORT_ERROR)
        return _health_checker_unavailable_response(503)

    try:
        checker = get_health_checker()
        health = _run_async(checker.get_dependency_health(), timeout=5)
        
        if health.get("status") == "healthy":
            return jsonify({
                "ready": True,
                "status": "healthy",
            }), 200
        else:
            return jsonify({
                "ready": False,
                "status": health.get("status", "unknown"),
                "missing_required": health.get("missing_required", []),
            }), 503
            
    except Exception as e:
        logger.error(f"Readiness probe failed: {e}")
        return jsonify({
            "ready": False,
            "status": "error",
            "error": str(e),
        }), 503


@metrics_bp.route("/live", methods=["GET"])
def liveness_probe():
    """
    Liveness probe endpoint.
    
    Simple endpoint to check if the application is alive.
    Does not perform any health checks - just confirms the process is running.
    
    Returns 200 if the application is running.
    """
    return jsonify({
        "alive": True,
        "timestamp": time.time(),
    }), 200


@metrics_bp.route("/metrics/summary", methods=["GET"])
def metrics_summary():
    """
    Human-readable metrics summary.
    
    Returns a JSON summary of key metrics instead of Prometheus format.
    Useful for quick debugging or dashboards that don't support Prometheus.
    """
    if get_metrics_collector is None:
        if _METRICS_IMPORT_ERROR is not None:
            logger.info("Metrics summary unavailable: %s", _METRICS_IMPORT_ERROR)
        return _metrics_unavailable_response()

    try:
        from prometheus_client import REGISTRY
        
        metrics = get_metrics_collector()
        metrics.update_system_metrics()
        
        # Extract key metrics from registry
        summary = {
            "system": {
                "cpu_percent": None,
                "memory_percent": None,
                "disk_percent": None,
            },
            "http": {
                "requests_total": 0,
                "requests_in_progress": 0,
                "error_rate": 0,
            },
            "cache": {
                "hits": 0,
                "misses": 0,
                "hit_ratio": 0,
            },
        }
        
        # Parse registry for summary values
        for collector in REGISTRY._names_to_collectors.values():
            try:
                for sample in collector.collect():
                    for s in sample.samples:
                        metric_name = s.name
                        
                        # System metrics
                        if metric_name == "system_cpu_usage_percent":
                            summary["system"]["cpu_percent"] = s.value
                        elif metric_name == "system_memory_usage_percent":
                            summary["system"]["memory_percent"] = s.value
                        elif metric_name == "system_disk_usage_percent":
                            summary["system"]["disk_percent"] = s.value
                        
                        # HTTP metrics
                        elif metric_name == "http_requests_total":
                            summary["http"]["requests_total"] += int(s.value)
                        elif metric_name == "http_requests_in_progress":
                            summary["http"]["requests_in_progress"] += int(s.value)
                        
                        # Cache metrics
                        elif metric_name == "cache_hits_total":
                            summary["cache"]["hits"] += int(s.value)
                        elif metric_name == "cache_misses_total":
                            summary["cache"]["misses"] += int(s.value)
                        
            except Exception:
                # Skip collectors that can't be read
                continue
        
        # Calculate error rate and hit ratio
        total_cache = summary["cache"]["hits"] + summary["cache"]["misses"]
        if total_cache > 0:
            summary["cache"]["hit_ratio"] = round(
                summary["cache"]["hits"] / total_cache, 4
            )
        
        return jsonify(summary), 200
        
    except Exception as e:
        logger.error(f"Failed to generate metrics summary: {e}")
        return jsonify({
            "error": "summary_generation_failed",
            "message": str(e),
        }), 500
