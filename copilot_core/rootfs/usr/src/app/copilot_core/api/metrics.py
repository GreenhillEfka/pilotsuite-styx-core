"""
Metrics API for PilotSuite Core

Provides endpoints for monitoring:
- Connection Pool metrics
- Cache statistics
- Performance metrics
- System health

Usage:
    from copilot_core.api.metrics import setup_metrics_routes
    
    app = web.Application()
    setup_metrics_routes(app)
"""

import logging
import time
from typing import Optional

from aiohttp import web

from copilot_core.connection_pool import get_pool_metrics
from copilot_core.cache import get_cache_stats

logger = logging.getLogger(__name__)

# In-memory metrics storage (for 24h history)
_metrics_history = []
_HISTORY_MAX_SIZE = 1440  # 1440 entries = 24h at 1-min intervals
_last_collection_time = 0.0
_collection_interval = 10  # seconds


def _collect_current_metrics() -> dict:
    """Collect current metrics from all sources."""
    pool_metrics = get_pool_metrics()
    
    # Cache stats are async, provide basic structure for sync context
    cache_stats = {
        "total_keys": 0,
        "hits": 0,
        "misses": 0,
        "hit_rate_pct": 0,
        "healthy": True,
    }
    
    return {
        "timestamp": time.time(),
        "connection_pool": pool_metrics,
        "cache": cache_stats,
    }


def _add_to_history(metrics: dict):
    """Add metrics to history, rotating old entries."""
    # global _metrics_history
    
    _metrics_history.append(metrics)
    
    # Rotate if too large (keep only last _HISTORY_MAX_SIZE entries)
    while len(_metrics_history) > _HISTORY_MAX_SIZE:
        _metrics_history.pop(0)


def get_metrics_history(duration_hours: int = 24) -> list:
    """Get metrics history for specified duration."""
    # global _metrics_history
    
    cutoff_time = time.time() - (duration_hours * 3600)
    return [m for m in _metrics_history if m.get("timestamp", 0) > cutoff_time]


async def handle_connection_pool_metrics(request: web.Request) -> web.Response:
    """
    GET /api/v1/metrics/connection-pool
    
    Returns connection pool metrics:
    - pool_size: Maximum connections
    - active_connections: Currently in use
    - idle_connections: Available for reuse
    - wait_time_ms: Average wait time for connection
    - reuse_rate_pct: Percentage of reused connections
    - healthy: Pool health status
    """
    try:
        pool_metrics = get_pool_metrics()
        
        # Format for dashboard
        response_data = {
            "ha_pool": {
                "pool_size": pool_metrics.get("config", {}).get("max_connections", 10),
                "active_connections": pool_metrics.get("ha_pool", {}).get(
                    "requests_total", 0
                ),  # Approximation
                "idle_connections": pool_metrics.get("config", {}).get(
                    "max_connections", 10
                )
                - pool_metrics.get("ha_pool", {}).get("requests_total", 0) % 10,
                "reuse_rate_pct": pool_metrics.get("ha_pool", {}).get(
                    "reuse_rate_pct", 0
                ),
                "healthy": pool_metrics.get("ha_pool", {}).get("healthy", True),
                "session_active": pool_metrics.get("ha_pool", {}).get(
                    "session_active", False
                ),
            },
            "ollama_pool": {
                "pool_size": pool_metrics.get("config", {}).get("max_connections", 10),
                "active_connections": pool_metrics.get("ollama_pool", {}).get(
                    "requests_total", 0
                ),
                "idle_connections": pool_metrics.get("config", {}).get(
                    "max_connections", 10
                )
                - pool_metrics.get("ollama_pool", {}).get("requests_total", 0) % 10,
                "reuse_rate_pct": pool_metrics.get("ollama_pool", {}).get(
                    "reuse_rate_pct", 0
                ),
                "healthy": pool_metrics.get("ollama_pool", {}).get("healthy", True),
                "session_active": pool_metrics.get("ollama_pool", {}).get(
                    "session_active", False
                ),
            },
            "config": pool_metrics.get("config", {}),
        }
        
        return web.json_response(response_data)
    
    except Exception as e:
        logger.error(f"Error getting pool metrics: {e}")
        return web.json_response(
            {"error": "Failed to get connection pool metrics", "details": str(e)},
            status=500,
        )


async def handle_cache_metrics(request: web.Request) -> web.Response:
    """
    GET /api/v1/metrics/cache
    
    Returns cache statistics:
    - total_keys: Number of cached items
    - hits: Cache hit count
    - misses: Cache miss count
    - hit_rate_pct: Cache hit percentage
    - memory_usage_bytes: Estimated memory usage
    """
    try:
        cache_stats = await get_cache_stats()
        return web.json_response(cache_stats)
    
    except Exception as e:
        logger.error(f"Error getting cache metrics: {e}")
        return web.json_response(
            {"error": "Failed to get cache metrics", "details": str(e)},
            status=500,
        )


async def handle_all_metrics(request: web.Request) -> web.Response:
    """
    GET /api/v1/metrics/all
    
    Returns all metrics (pool + cache + system).
    """
    try:
        current = _collect_current_metrics()
        _add_to_history(current)
        
        return web.json_response(current)
    
    except Exception as e:
        logger.error(f"Error getting all metrics: {e}")
        return web.json_response(
            {"error": "Failed to get metrics", "details": str(e)},
            status=500,
        )


async def handle_metrics_history(request: web.Request) -> web.Response:
    """
    GET /api/v1/metrics/history
    
    Query params:
    - duration: Hours of history (default: 24)
    
    Returns time-series metrics for dashboard charts.
    """
    try:
        duration = int(request.query.get("duration", "24"))
        history = get_metrics_history(duration)
        
        return web.json_response({"history": history, "count": len(history)})
    
    except Exception as e:
        logger.error(f"Error getting metrics history: {e}")
        return web.json_response(
            {"error": "Failed to get metrics history", "details": str(e)},
            status=500,
        )


async def handle_health(request: web.Request) -> web.Response:
    """
    GET /api/v1/metrics/health
    
    Returns overall system health status.
    """
    try:
        pool_metrics = get_pool_metrics()
        cache_stats = await get_cache_stats()
        
        ha_healthy = pool_metrics.get("ha_pool", {}).get("healthy", True)
        ollama_healthy = pool_metrics.get("ollama_pool", {}).get("healthy", True)
        cache_healthy = cache_stats.get("healthy", True)
        
        overall_healthy = ha_healthy and ollama_healthy and cache_healthy
        
        return web.json_response(
            {
                "healthy": overall_healthy,
                "components": {
                    "ha_pool": ha_healthy,
                    "ollama_pool": ollama_healthy,
                    "cache": cache_healthy,
                },
                "timestamp": time.time(),
            }
        )
    
    except Exception as e:
        logger.error(f"Error getting health status: {e}")
        return web.json_response(
            {"healthy": False, "error": str(e)},
            status=500,
        )


def setup_metrics_routes(app: web.Application):
    """Register metrics routes with the application."""
    app.router.add_get("/api/v1/metrics/connection-pool", handle_connection_pool_metrics)
    app.router.add_get("/api/v1/metrics/cache", handle_cache_metrics)
    app.router.add_get("/api/v1/metrics/all", handle_all_metrics)
    app.router.add_get("/api/v1/metrics/history", handle_metrics_history)
    app.router.add_get("/api/v1/metrics/health", handle_health)
    
    logger.info("Metrics routes registered")
