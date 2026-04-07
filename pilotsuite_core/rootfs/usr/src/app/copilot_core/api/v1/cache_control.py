"""Cache Control API Endpoints.

Provides REST API for cache management:
- GET /api/v1/cache/status — Cache status
- POST /api/v1/cache/invalidate — Invalidate cache
- GET /api/v1/cache/stats — Hit/miss statistics
"""
from __future__ import annotations

import asyncio
import logging
from typing import Any

from flask import Blueprint, jsonify, request

try:
    from copilot_core.api.security import require_token
except ImportError:
    from ..api.security import require_token

try:
    from copilot_core.cache.redis_client import get_redis_client
    from copilot_core.cache.api_cache import get_api_cache
except ImportError:
    from ...cache.redis_client import get_redis_client
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


def _error(message: str, status_code: int):
    return jsonify({"success": False, "error": message}), status_code


def _get_optional_json_object() -> tuple[dict[str, Any] | None, Any | None]:
    raw_body = request.get_data(cache=True)
    if not raw_body:
        return {}, None

    payload = request.get_json(silent=True)
    if payload is None or not isinstance(payload, dict):
        return None, _error("JSON object required", 400)
    return payload, None


def _get_cache_or_error():
    cache = get_api_cache()
    if cache is None:
        return None, _error("cache not initialized", 503)
    return cache, None


def _get_redis_client_or_error():
    redis_client = get_redis_client()
    if redis_client is None:
        return None, _error("cache client not initialized", 503)
    return redis_client, None


def _optional_bool_field(data: dict[str, Any], field: str):
    if field not in data:
        return None, None
    value = data[field]
    if not isinstance(value, bool):
        return None, _error(f"{field} must be a boolean", 400)
    return value, None


def _optional_non_empty_string_field(data: dict[str, Any], field: str):
    if field not in data:
        return None, None
    value = data[field]
    if not isinstance(value, str) or not value.strip():
        return None, _error(f"{field} must be a non-empty string", 400)
    return value.strip(), None


@cache_control_bp.route("/status", methods=["GET"])
@require_token
def cache_status():
    """Get cache connection status.

    Returns:
        JSON with connection status and configuration
    """
    try:
        redis_client, error_response = _get_redis_client_or_error()
        if error_response:
            return error_response

        connected = bool(getattr(redis_client, "is_connected", False))
        return jsonify({
            "success": True,
            "data": {
                "connected": connected,
                "host": getattr(redis_client, "host", None),
                "port": getattr(redis_client, "port", None),
                "using_fallback": not connected,
                "redis_available": connected,
            }
        }), 200

    except Exception as e:
        logger.exception("Error getting cache status")
        return _error(str(e), 500)


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
        cache, error_response = _get_cache_or_error()
        if error_response:
            return error_response

        data, error_response = _get_optional_json_object()
        if error_response:
            return error_response
        assert data is not None

        clear_all, error_response = _optional_bool_field(data, "all")
        if error_response:
            return error_response

        key, error_response = _optional_non_empty_string_field(data, "key")
        if error_response:
            return error_response

        pattern, error_response = _optional_non_empty_string_field(data, "pattern")
        if error_response:
            return error_response

        if clear_all:
            _run_async(cache.invalidate_all())
            return jsonify({
                "success": True,
                "data": {
                    "invalidated": "all",
                    "message": "All cache entries cleared",
                }
            }), 200

        if key is not None:
            success = _run_async(cache.invalidate(key))
            return jsonify({
                "success": success,
                "data": {
                    "key": key,
                    "invalidated": success,
                }
            }), 200 if success else 404

        if pattern is not None:
            count = _run_async(cache.invalidate_pattern(pattern))
            return jsonify({
                "success": True,
                "data": {
                    "pattern": pattern,
                    "invalidated_count": count,
                }
            }), 200

        entity_count = _run_async(cache.invalidate_entities())
        state_count = _run_async(cache.invalidate_states())
        return jsonify({
            "success": True,
            "data": {
                "invalidated_entities": entity_count,
                "invalidated_states": state_count,
                "total": entity_count + state_count,
            }
        }), 200

    except Exception as e:
        logger.exception("Error invalidating cache")
        return _error(str(e), 500)


@cache_control_bp.route("/stats", methods=["GET"])
@require_token
def cache_stats():
    """Get cache statistics.

    Returns:
        JSON with hit/miss ratio and connection stats
    """
    try:
        cache, error_response = _get_cache_or_error()
        if error_response:
            return error_response

        stats = _run_async(cache.get_stats())
        return jsonify({
            "success": True,
            "data": stats,
        }), 200

    except Exception as e:
        logger.exception("Error getting cache stats")
        return _error(str(e), 500)


def init_cache_control_api(app=None) -> None:
    """Initialize cache control API.

    Args:
        app: Optional Flask app to register blueprint
    """
    redis_client = get_redis_client()

    if redis_client is not None:
        try:
            _run_async(redis_client.connect(), timeout=5)
        except Exception as e:
            logger.warning("Initial Redis connection failed: %s", e)

    if app:
        app.register_blueprint(cache_control_bp, url_prefix="/api/v1/cache")

    logger.info("Cache Control API initialized")
