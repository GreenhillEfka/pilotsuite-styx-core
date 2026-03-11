"""Cache Control API Endpoints.

Provides REST API for cache management:
- GET /api/v1/cache/status — Cache status
- POST /api/v1/cache/invalidate — Invalidate cache
- GET /api/v1/cache/stats — Hit/miss statistics
"""
from __future__ import annotations

import asyncio
import logging
from typing import Optional

from flask import Blueprint, jsonify, request

try:
    from copilot_core.api.security import require_token
except ImportError:
    from ..api.security import require_token

try:
    from copilot_core.cache.redis_client import get_redis_client, init_redis_client
    from copilot_core.cache.api_cache import get_api_cache
except ImportError:
    from ...cache.redis_client import get_redis_client, init_redis_client
    from ...cache.api_cache import get_api_cache

logger = logging.getLogger(__name__)

cache_control_bp = Blueprint("cache_control", __name__)


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


@cache_control_bp.route("/status", methods=["GET"])
@require_token
def cache_status():
    """Get cache connection status.
    
    Returns:
        JSON with connection status and configuration
    """
    try:
        redis_client = get_redis_client()
        
        return jsonify({
            "success": True,
            "data": {
                "connected": redis_client.is_connected,
                "host": redis_client.host,
                "port": redis_client.port,
                "using_fallback": not redis_client.is_connected,
                "redis_available": redis_client.is_connected
            }
        }), 200
    
    except Exception as e:
        logger.error(f"Error getting cache status: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@cache_control_bp.route("/invalidate", methods=["POST"])
@require_token
def cache_invalidate():
    """Invalidate cache entries.
    
    Request JSON:
        - pattern: Optional pattern to match (e.g., "entity:*")
        - key: Optional specific key to invalidate
        - all: Optional boolean to clear all cache
    
    Returns:
        JSON with invalidation results
    """
    try:
        from ..cache.api_cache import get_api_cache

        cache = get_api_cache()
        data = request.get_json() or {}

        if data.get("all"):
            _run_async(cache.invalidate_all())
            return jsonify({
                "success": True,
                "data": {
                    "invalidated": "all",
                    "message": "All cache entries cleared"
                }
            }), 200

        elif data.get("key"):
            key = data["key"]
            success = _run_async(cache.invalidate(key))
            return jsonify({
                "success": success,
                "data": {
                    "key": key,
                    "invalidated": success
                }
            }), 200 if success else 404

        elif data.get("pattern"):
            pattern = data["pattern"]
            count = _run_async(cache.invalidate_pattern(pattern))
            return jsonify({
                "success": True,
                "data": {
                    "pattern": pattern,
                    "invalidated_count": count
                }
            }), 200

        else:
            entity_count = _run_async(cache.invalidate_entities())
            state_count = _run_async(cache.invalidate_states())
            return jsonify({
                "success": True,
                "data": {
                    "invalidated_entities": entity_count,
                    "invalidated_states": state_count,
                    "total": entity_count + state_count
                }
            }), 200
    
    except Exception as e:
        logger.error(f"Error invalidating cache: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@cache_control_bp.route("/stats", methods=["GET"])
@require_token
def cache_stats():
    """Get cache statistics.
    
    Returns:
        JSON with hit/miss ratio and connection stats
    """
    try:
        from ..cache.api_cache import get_api_cache

        cache = get_api_cache()
        stats = _run_async(cache.get_stats())

        return jsonify({
            "success": True,
            "data": stats
        }), 200

    except Exception as e:
        logger.error(f"Error getting cache stats: {e}")
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


def init_cache_control_api(app=None) -> None:
    """Initialize cache control API.
    
    Args:
        app: Optional Flask app to register blueprint
    """
    # Initialize Redis client
    redis_client = get_redis_client()

    # Try to connect (non-blocking)
    try:
        _run_async(redis_client.connect(), timeout=5)
    except Exception as e:
        logger.warning("Initial Redis connection failed: %s", e)
    
    if app:
        app.register_blueprint(cache_control_bp, url_prefix="/api/v1/cache")
    
    logger.info("Cache Control API initialized")
