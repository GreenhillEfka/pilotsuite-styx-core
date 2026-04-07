"""
Performance API endpoints for monitoring and cache management.

Includes:
- Cache statistics and management
- Connection pool metrics (SQL, HA, Ollama)
- Async executor status
- Performance metrics recording
"""

import time
from flask import Blueprint, jsonify, request
from typing import Dict, Any

from ..performance import (
    brain_graph_cache,
    ml_cache,
    api_response_cache,
    sql_pool,
    async_executor,
    perf_monitor,
    get_performance_stats,
    reset_performance_stats,
)
from .security import require_api_key

# Try to import connection pool metrics (optional, for async pooling)
try:
    from ..connection_pool import get_pool_metrics as get_async_pool_metrics
    HAS_ASYNC_POOL = True
except ImportError:
    HAS_ASYNC_POOL = False
    def get_async_pool_metrics():
        return {"error": "Async pool not available"}

# Create blueprint
performance_bp = Blueprint('performance', __name__, url_prefix='/api/v1/performance')


@performance_bp.route('/stats', methods=['GET'])
@require_api_key
def get_stats() -> Dict[str, Any]:
    """
    Get performance statistics.
    
    Returns:
    - Cache statistics (hits, misses, hit rate, size)
    - Connection pool status
    - Async executor status
    """
    return jsonify({
        "version": 1,
        "timestamp_ms": int(time.time() * 1000),
        **get_performance_stats(),
    })


@performance_bp.route('/cache/clear', methods=['POST'])
@require_api_key
def clear_caches() -> Dict[str, Any]:
    """
    Clear all caches.
    
    Useful after major changes or for testing.
    """
    brain_graph_cache.clear()
    ml_cache.clear()
    api_response_cache.clear()
    
    return jsonify({
        "message": "All caches cleared",
        "timestamp_ms": int(time.time() * 1000),
    })


@performance_bp.route('/cache/<cache_name>', methods=['POST'])
@require_api_key
def clear_specific_cache(cache_name: str) -> Dict[str, Any]:
    """
    Clear a specific cache.
    
    Args:
        cache_name: brain_graph, ml, or api
    """
    cache_map = {
        "brain_graph": brain_graph_cache,
        "ml": ml_cache,
        "api": api_response_cache,
    }
    
    if cache_name not in cache_map:
        return jsonify({"error": f"Unknown cache: {cache_name}"}), 400
    
    cache = cache_map[cache_name]
    cache.clear()
    
    return jsonify({
        "message": f"Cache '{cache_name}' cleared",
        "timestamp_ms": int(time.time() * 1000),
    })


@performance_bp.route('/cache/invalidate', methods=['POST'])
@require_api_key
def invalidate_pattern() -> Dict[str, Any]:
    """
    Invalidate cache entries matching a pattern.
    
    JSON body:
    - cache: brain_graph, ml, or api
    - pattern: string to match in cache keys
    """
    from flask import request
    
    data = request.get_json() or {}
    cache_name = data.get("cache", "")
    pattern = data.get("pattern", "")
    
    if not pattern:
        return jsonify({"error": "pattern is required"}), 400
    
    cache_map = {
        "brain_graph": brain_graph_cache,
        "ml": ml_cache,
        "api": api_response_cache,
    }
    
    if cache_name and cache_name not in cache_map:
        return jsonify({"error": f"Unknown cache: {cache_name}"}), 400
    
    if cache_name:
        # Invalidate specific cache
        count = cache_map[cache_name].invalidate_pattern(pattern)
    else:
        # Invalidate all caches
        count = 0
        for cache in cache_map.values():
            count += cache.invalidate_pattern(pattern)
    
    return jsonify({
        "message": f"Invalidated {count} cache entries matching '{pattern}'",
        "count": count,
        "timestamp_ms": int(time.time() * 1000),
    })


@performance_bp.route('/cache/cleanup', methods=['POST'])
@require_api_key
def cleanup_expired_caches() -> Dict[str, Any]:
    """Remove expired entries from all caches."""
    removed = 0
    removed += brain_graph_cache.cleanup_expired()
    removed += ml_cache.cleanup_expired()
    removed += api_response_cache.cleanup_expired()

    return jsonify({
        "message": f"Removed {removed} expired cache entries",
        "removed": removed,
        "timestamp_ms": int(time.time() * 1000),
    })


@performance_bp.route('/pool/status', methods=['GET'])
@require_api_key
def get_pool_status() -> Dict[str, Any]:
    """
    Get SQL connection pool status.
    
    Returns:
    - Pool size (active, idle, max)
    - Connection reuse rate
    - Query performance metrics
    """
    return jsonify({
        "version": 1,
        "timestamp_ms": int(time.time() * 1000),
        **sql_pool.get_stats(),
    })


@performance_bp.route('/pool/cleanup', methods=['POST'])
@require_api_key
def cleanup_pool() -> Dict[str, Any]:
    """Clean up idle connections in the pool."""
    removed = sql_pool.cleanup_idle()
    
    return jsonify({
        "message": f"Removed {removed} idle connections",
        "removed": removed,
        "timestamp_ms": int(time.time() * 1000),
    })


@performance_bp.route('/pool/metrics', methods=['GET'])
@require_api_key
def get_pool_metrics() -> Dict[str, Any]:
    """
    Get comprehensive connection pool metrics.
    
    Returns metrics for:
    - SQL connection pool (sync)
    - HA async connection pool
    - Ollama async connection pool
    
    Query parameters:
    - pool: sql, ha, ollama, or all (default: all)
    """
    pool_type = request.args.get("pool", "all")
    
    metrics = {
        "version": 1,
        "timestamp_ms": int(time.time() * 1000),
    }
    
    if pool_type in ["all", "sql"]:
        metrics["sql_pool"] = sql_pool.get_stats()
    
    if pool_type in ["all", "ha", "ollama"] and HAS_ASYNC_POOL:
        async_metrics = get_async_pool_metrics()
        if "error" not in async_metrics:
            if pool_type == "all":
                metrics["async_pools"] = async_metrics
            elif pool_type == "ha":
                metrics["ha_pool"] = async_metrics.get("ha_pool", {})
            elif pool_type == "ollama":
                metrics["ollama_pool"] = async_metrics.get("ollama_pool", {})
        else:
            metrics["async_pools"] = async_metrics
    elif not HAS_ASYNC_POOL:
        metrics["async_pools"] = {"status": "not_available", "reason": "connection_pool module not found"}
    
    return jsonify(metrics)


@performance_bp.route('/pool/metrics/summary', methods=['GET'])
@require_api_key
def get_pool_metrics_summary() -> Dict[str, Any]:
    """
    Get summarized connection pool health status.
    
    Returns a quick health check for dashboard integration:
    - Overall pool health (healthy/degraded/unhealthy)
    - Key metrics (reuse rates, active connections)
    - Recommendations if issues detected
    """
    sql_stats = sql_pool.get_stats()
    
    # Determine health status
    health_status = "healthy"
    recommendations = []
    
    # Check SQL pool health
    sql_active = sql_stats.get("active_connections", 0)
    sql_max = sql_stats.get("max_connections", 100)
    sql_usage_pct = (sql_active / max(sql_max, 1)) * 100
    
    if sql_usage_pct > 90:
        health_status = "unhealthy"
        recommendations.append("SQL pool near capacity - consider increasing max_connections")
    elif sql_usage_pct > 75:
        health_status = "degraded"
        recommendations.append("SQL pool usage high - monitor closely")
    
    # Check async pool health if available
    if HAS_ASYNC_POOL:
        async_metrics = get_async_pool_metrics()
        if "error" not in async_metrics:
            ha_pool = async_metrics.get("ha_pool", {})
            ollama_pool = async_metrics.get("ollama_pool", {})
            
            ha_reuse = ha_pool.get("reuse_rate_pct", 0)
            ollama_reuse = ollama_pool.get("reuse_rate_pct", 0)
            
            if ha_reuse < 50:
                if health_status == "healthy":
                    health_status = "degraded"
                recommendations.append(f"HA connection reuse low ({ha_reuse}%) - check for connection leaks")
            
            if ollama_reuse < 50:
                if health_status == "healthy":
                    health_status = "degraded"
                recommendations.append(f"Ollama connection reuse low ({ollama_reuse}%) - check for connection leaks")
    
    return jsonify({
        "version": 1,
        "timestamp_ms": int(time.time() * 1000),
        "health": {
            "status": health_status,
            "sql_pool": {
                "active": sql_active,
                "max": sql_max,
                "usage_pct": round(sql_usage_pct, 1),
            },
            "recommendations": recommendations,
        }
    })


@performance_bp.route('/metrics', methods=['GET'])
@require_api_key
def get_metrics() -> Dict[str, Any]:
    """
    Get recorded performance metrics.
    
    Query parameters:
    - name: metric name (optional, returns all if not specified)
    """
    from flask import request
    
    name = request.args.get("name")
    
    if name:
        return jsonify({
            "version": 1,
            "timestamp_ms": int(time.time() * 1000),
            name: perf_monitor.get_stats(name),
        })
    else:
        return jsonify({
            "version": 1,
            "timestamp_ms": int(time.time() * 1000),
            **perf_monitor.get_all_stats(),
        })


@performance_bp.route('/metrics/reset', methods=['POST'])
@require_api_key
def reset_metrics() -> Dict[str, Any]:
    """Reset all recorded metrics."""
    perf_monitor.reset()
    reset_performance_stats()
    
    return jsonify({
        "message": "Metrics and cache stats reset",
        "timestamp_ms": int(time.time() * 1000),
    })
