"""
Rate Limit Configuration API

Endpoints for managing rate limit settings per API key/client.

Endpoints:
- GET /api/v1/rate-limit/config - Get current rate limit config
- PUT /api/v1/rate-limit/config - Update rate limit config
- GET /api/v1/rate-limit/status - Get rate limit status for all clients
- DELETE /api/v1/rate-limit/config/{client_id} - Reset client's rate limit
- POST /api/v1/rate-limit/reset-all - Reset all rate limits (admin)
"""

from __future__ import annotations

import logging
from typing import Any

from flask import Blueprint, jsonify, request

from copilot_core.models.rate_limit import (
    RateLimitAlgorithm,
    RateLimitConfig,
    DEFAULT_RATE_LIMIT_CONFIG,
)
from copilot_core.api.middleware.rate_limit import (
    extract_client_id,
    get_rate_limit_store,
)
from copilot_core.api.security import require_admin

logger = logging.getLogger(__name__)

# Create blueprint with relative prefix (will be nested under /api/v1)
rate_limit_bp = Blueprint("rate_limit", __name__, url_prefix="/api/v1/rate-limit")

# Validation boundaries for client-provided config updates.
_MIN_REQUESTS_PER_MINUTE = 1
_MAX_REQUESTS_PER_MINUTE = 10_000
_MIN_BURST_SIZE = 1
_MAX_BURST_SIZE = 10_000
_MAX_CLIENT_ID_LEN = 256

# Validation boundaries for cleanup age in seconds.
_MIN_CLEANUP_AGE_SECONDS = 1
_MAX_CLEANUP_AGE_SECONDS = 604_800


def _normalize_client_id(client_id: Any) -> str:
    """Normalize and validate a client identifier."""
    normalized = (str(client_id) if client_id is not None else "").strip()
    if not normalized:
        raise ValueError("client_id must be a non-empty string")
    if len(normalized) > _MAX_CLIENT_ID_LEN:
        raise ValueError(f"client_id must be at most {_MAX_CLIENT_ID_LEN} characters")
    return normalized


def _validate_int_bound(
    name: str,
    value: Any,
    min_value: int,
    max_value: int,
) -> int:
    """Validate integer values for rate-limit configuration."""
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        raise ValueError(f"{name} must be an integer")

    if parsed < min_value or parsed > max_value:
        raise ValueError(f"{name} must be between {min_value} and {max_value}")

    return parsed


@rate_limit_bp.route("/rate-limit/config", methods=["GET"])
def get_rate_limit_config():
    """
    Get rate limit configuration.

    Query params:
    - client_id: Optional client identifier (default: current request's client)

    Returns:
        Rate limit configuration for the specified or current client.
    """
    try:
        client_id = request.args.get("client_id")

        if not client_id:
            client_id = extract_client_id()

        store = get_rate_limit_store()
        config = store.get_config(client_id)

        if config:
            return jsonify({
                "client_id": client_id,
                "config": config.to_dict(),
                "is_default": config == DEFAULT_RATE_LIMIT_CONFIG,
            }), 200
        else:
            return jsonify({
                "client_id": client_id,
                "config": DEFAULT_RATE_LIMIT_CONFIG.to_dict(),
                "is_default": True,
            }), 200

    except Exception as e:
        logger.error(f"Failed to get rate limit config: {e}")
        return jsonify({
            "error": "config_fetch_failed",
            "message": str(e),
        }), 500


@rate_limit_bp.route("/rate-limit/config", methods=["PUT"])
@require_admin
def update_rate_limit_config():
    """
    Update rate limit configuration for a client.

    Body (JSON):
    {
        "client_id": "apikey:xxx",  # Optional, defaults to current client
        "requests_per_minute": 100,  # Optional
        "burst_size": 20,  # Optional
        "algorithm": "token_bucket",  # Optional
        "enabled": true  # Optional
    }

    Returns:
        Updated configuration.
    """
    try:
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object")

        client_id = _normalize_client_id(data.get("client_id") or extract_client_id())

        # Build config from defaults to avoid mutating DEFAULT_RATE_LIMIT_CONFIG.
        config = RateLimitConfig.from_dict(DEFAULT_RATE_LIMIT_CONFIG.to_dict())

        # Override with provided values.
        if "requests_per_minute" in data:
            config.requests_per_minute = _validate_int_bound(
                "requests_per_minute",
                data["requests_per_minute"],
                _MIN_REQUESTS_PER_MINUTE,
                _MAX_REQUESTS_PER_MINUTE,
            )
        if "burst_size" in data:
            config.burst_size = _validate_int_bound(
                "burst_size",
                data["burst_size"],
                _MIN_BURST_SIZE,
                _MAX_BURST_SIZE,
            )
        if "algorithm" in data:
            config.algorithm = RateLimitAlgorithm(data["algorithm"])
        if "enabled" in data:
            config.enabled = bool(data["enabled"])
        if "api_key" in data:
            config.api_key = data.get("api_key")

        # Update store
        store = get_rate_limit_store()
        store.update_config(client_id, config)

        logger.info(
            f"Updated rate limit config for {client_id}: "
            f"{config.requests_per_minute} req/min, burst {config.burst_size}"
        )

        return jsonify({
            "client_id": client_id,
            "config": config.to_dict(),
            "message": "Rate limit configuration updated",
        }), 200

    except ValueError as e:
        logger.warning(f"Invalid rate limit config: {e}")
        return jsonify({
            "error": "invalid_config",
            "message": str(e),
        }), 400
    except Exception as e:
        logger.error(f"Failed to update rate limit config: {e}")
        return jsonify({
            "error": "config_update_failed",
            "message": str(e),
        }), 500


@rate_limit_bp.route("/rate-limit/status", methods=["GET"])
def get_rate_limit_status():
    """
    Get rate limit status for all tracked clients.

    Returns:
        Status for all clients with active rate limit buckets.
    """
    try:
        store = get_rate_limit_store()
        all_status = store.get_all_status()

        # Add summary
        total_clients = len(all_status)
        limited_clients = sum(
            1 for status in all_status.values()
            if status["bucket"]["tokens"] < 1
        )

        return jsonify({
            "total_clients": total_clients,
            "limited_clients": limited_clients,
            "clients": all_status,
        }), 200

    except Exception as e:
        logger.error(f"Failed to get rate limit status: {e}")
        return jsonify({
            "error": "status_fetch_failed",
            "message": str(e),
        }), 500


@rate_limit_bp.route("/rate-limit/status/<path:client_id>", methods=["GET"])
def get_client_rate_limit_status(client_id: str):
    """
    Get rate limit status for a specific client.

    Args:
        client_id: Client identifier (e.g., "apikey:xxx" or "ip:1.2.3.4")

    Returns:
        Status for the specified client.
    """
    try:
        store = get_rate_limit_store()
        config = store.get_config(client_id)

        if not config:
            return jsonify({
                "error": "client_not_found",
                "message": f"No rate limit config for client: {client_id}",
            }), 404

        bucket = store.get_bucket(client_id, config)

        return jsonify({
            "client_id": client_id,
            "config": config.to_dict(),
            "bucket": bucket.to_dict(),
            "is_limited": bucket.tokens < 1,
        }), 200

    except Exception as e:
        logger.error(f"Failed to get client rate limit status: {e}")
        return jsonify({
            "error": "status_fetch_failed",
            "message": str(e),
        }), 500


@rate_limit_bp.route("/rate-limit/config/<path:client_id>", methods=["DELETE"])
@require_admin
def reset_client_rate_limit(client_id: str):
    """
    Reset rate limit for a specific client.

    This removes the client's bucket, allowing them to start fresh.

    Args:
        client_id: Client identifier to reset
    """
    try:
        store = get_rate_limit_store()
        store.remove_client(client_id)

        logger.info(f"Reset rate limit for client: {client_id}")

        return jsonify({
            "client_id": client_id,
            "message": "Rate limit reset successfully",
        }), 200

    except Exception as e:
        logger.error(f"Failed to reset client rate limit: {e}")
        return jsonify({
            "error": "reset_failed",
            "message": str(e),
        }), 500


@rate_limit_bp.route("/rate-limit/reset-all", methods=["POST"])
@require_admin
def reset_all_rate_limits():
    """
    Reset all rate limits (admin operation).

    Clears all client buckets. Use with caution.
    """
    try:
        store = get_rate_limit_store()
        all_status = store.get_all_status()
        client_count = len(all_status)

        # Clear all clients
        for client_id in list(all_status.keys()):
            store.remove_client(client_id)

        logger.info(f"Reset all rate limits: {client_count} clients cleared")

        return jsonify({
            "message": "All rate limits reset",
            "clients_cleared": client_count,
        }), 200

    except Exception as e:
        logger.error(f"Failed to reset all rate limits: {e}")
        return jsonify({
            "error": "reset_all_failed",
            "message": str(e),
        }), 500


@rate_limit_bp.route("/rate-limit/cleanup", methods=["POST"])
@require_admin
def cleanup_stale_rate_limits():
    """
    Clean up stale rate limit buckets.

    Removes buckets for clients inactive for more than 1 hour.

    Body (JSON):
    {
        "max_age_seconds": 3600  # Optional, default: 3600
    }
    """
    try:
        data = request.get_json(silent=True) or {}
        if not isinstance(data, dict):
            raise ValueError("Request body must be a JSON object")

        max_age = _validate_int_bound(
            "max_age_seconds",
            data.get("max_age_seconds", 3600),
            _MIN_CLEANUP_AGE_SECONDS,
            _MAX_CLEANUP_AGE_SECONDS,
        )

        store = get_rate_limit_store()
        removed = store.cleanup_stale(max_age_seconds=max_age)

        logger.info(f"Cleaned up {removed} stale rate limit buckets")

        return jsonify({
            "message": "Stale rate limits cleaned up",
            "buckets_removed": removed,
            "max_age_seconds": max_age,
        }), 200

    except ValueError as e:
        logger.warning(f"Invalid cleanup payload: {e}")
        return jsonify({
            "error": "invalid_config",
            "message": str(e),
        }), 400
    except Exception as e:
        logger.error(f"Failed to cleanup stale rate limits: {e}")
        return jsonify({
            "error": "cleanup_failed",
            "message": str(e),
        }), 500


@rate_limit_bp.route("/rate-limit/defaults", methods=["GET"])
def get_default_rate_limit():
    """
    Get default rate limit configuration.

    Returns the system-wide default rate limit settings.
    """
    return jsonify({
        "defaults": DEFAULT_RATE_LIMIT_CONFIG.to_dict(),
        "description": {
            "requests_per_minute": "Maximum sustained request rate",
            "burst_size": "Maximum burst capacity (token bucket size)",
            "algorithm": "Rate limiting algorithm (token_bucket)",
            "refill_rate": "Tokens added per second",
        }
    }), 200
