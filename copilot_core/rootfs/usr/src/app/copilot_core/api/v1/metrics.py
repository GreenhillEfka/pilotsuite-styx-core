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

import logging
import asyncio
import time
from typing import Any, Dict

from flask import Blueprint, Response, jsonify, request


def _run_async(coro, timeout: int = 10):
    """Run async coroutine from sync Flask context."""
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

from copilot_core.monitoring.metrics import get_prometheus_metrics, get_metrics_collector
from copilot_core.monitoring.health import get_health_checker

logger = logging.getLogger(__name__)

# Create blueprint with relative prefix (will be nested under /api/v1)
metrics_bp = Blueprint("metrics", __name__)


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

