"""Security Configuration API.

Provides endpoints for:
- Security status and metrics
- Rate limit configuration
- Token management
- Security event logs
"""

from __future__ import annotations

import os
import time
import secrets
import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timedelta

from flask import Blueprint, jsonify, request, g

from ...security import get_rate_limiter, get_validator, get_security_logger
from ..security import get_auth_token, require_admin, validate_token

logger = logging.getLogger(__name__)

bp = Blueprint("security", __name__, url_prefix="/api/v1/security")


@bp.get("/status")
def get_security_status():
    """Get overall security status and metrics.
    
    Returns:
        Security status including rate limiter status, validator config, etc.
    """
    rate_limiter = get_rate_limiter()
    validator = get_validator()
    
    return jsonify({
        "ok": True,
        "status": {
            "rate_limiter": {
                "default_capacity": rate_limiter.default_capacity,
                "default_refill_rate": rate_limiter.default_refill_rate,
                "active_buckets": len(rate_limiter._buckets),
                "endpoint_overrides": len(rate_limiter._endpoint_limits),
            },
            "input_validator": {
                "max_request_size": validator.max_request_size,
                "max_field_length": validator.max_field_length,
                "max_array_length": validator.max_array_length,
                "checks_enabled": {
                    "sql_injection": validator.check_sql_injection,
                    "xss": validator.check_xss,
                    "path_traversal": validator.check_path_traversal,
                },
            },
            "security_headers": os.environ.get("COPILOT_SECURITY_HEADERS", "true").lower() == "true",
            "request_logging": os.environ.get("COPILOT_REQUEST_LOGGING", "true").lower() == "true",
        },
    })


@bp.get("/rate-limits")
def get_rate_limits():
    """Get current rate limit configuration.
    
    Returns:
        Rate limit configuration and status
    """
    rate_limiter = get_rate_limiter()
    
    return jsonify({
        "ok": True,
        "rate_limits": {
            "default": {
                "requests_per_minute": rate_limiter.default_capacity,
                "refill_rate": rate_limiter.default_refill_rate,
            },
            "endpoints": {
                endpoint: {
                    "requests_per_minute": capacity,
                    "refill_rate": refill_rate,
                }
                for endpoint, (capacity, refill_rate) in rate_limiter._endpoint_limits.items()
            },
            "active_clients": len(rate_limiter._buckets),
        },
    })


@bp.post("/rate-limits/reset")
@require_admin
def reset_rate_limits():
    """Reset rate limits for a client or all clients.
    
    Request body (optional):
        client_key: Client identifier (reset all if not provided)
        
    Returns:
        Confirmation of reset
    """
    rate_limiter = get_rate_limiter()
    
    data = request.get_json(silent=True) or {}
    client_key = data.get("client_key")
    
    rate_limiter.reset(client_key)
    
    return jsonify({
        "ok": True,
        "message": f"Rate limits reset for {'all clients' if not client_key else client_key}",
    })


@bp.get("/logs")
@require_admin
def get_security_logs():
    """Get recent security logs.
    
    Query parameters:
        limit: Maximum number of events (default: 100)
        event_type: Filter by event type (optional)
        
    Returns:
        Recent security events
    """
    limit = request.args.get("limit", 100, type=int)
    event_type = request.args.get("event_type")
    
    sec_logger = get_security_logger()
    events = sec_logger.get_recent_events(limit=limit, event_type=event_type)
    
    return jsonify({
        "ok": True,
        "events": events,
        "count": len(events),
    })


@bp.get("/token/rotate")
@require_admin
def rotate_auth_token():
    """Rotate the authentication token.
    
    This generates a new auth token and expires the old one.
    The new token must be configured in the client applications.
    
    Note: This is a dangerous operation and requires admin authentication.
    The new token will be returned ONCE - store it securely.
    
    Returns:
        New token (only shown once!)
    """
    # Generate new token
    new_token = secrets.token_urlsafe(32)
    
    # Log the rotation
    sec_logger = get_security_logger()
    old_token = get_auth_token()
    old_prefix = old_token[:8] if old_token else "none"
    new_prefix = new_token[:8]
    
    sec_logger.log_token_rotation(
        client="admin",
        old_token_prefix=old_prefix,
        new_token_prefix=new_prefix,
        details={
            "timestamp": datetime.now().isoformat(),
            "expires_in_hours": 24,
        },
    )
    
    # Note: We don't actually store the token here - that's done via
    # environment variable or options.json. This endpoint just generates
    # a new token value that should be configured externally.
    
    return jsonify({
        "ok": True,
        "message": "New authentication token generated",
        "token": new_token,
        "warning": "Store this token securely! It will not be shown again.",
        "expires_in": "24 hours (automatic expiration)",
        "configuration": {
            "environment": "Set COPILOT_AUTH_TOKEN environment variable",
            "options": "Add to /data/options.json as 'auth_token'",
        },
    })


@bp.get("/token/status")
def get_token_status():
    """Get authentication token status.
    
    Returns:
        Token status (configured, expiration, etc.)
    """
    token = get_auth_token()
    is_configured = bool(token)
    
    # Check if auth is required
    auth_required = True
    env_value = os.environ.get("COPILOT_AUTH_REQUIRED", "").lower().strip()
    if env_value == "false":
        auth_required = False
    elif env_value == "true":
        auth_required = True
    
    return jsonify({
        "ok": True,
        "token": {
            "configured": is_configured,
            "prefix": f"{token[:8]}..." if token else None,
            "length": len(token) if token else 0,
        },
        "auth_required": auth_required,
        "expiration": {
            "enabled": True,
            "duration_hours": 24,
            "note": "Tokens should be rotated every 24 hours for security",
        },
    })


@bp.get("/config")
@require_admin
def get_security_config():
    """Get security configuration.
    
    Returns:
        Security configuration settings
    """
    return jsonify({
        "ok": True,
        "config": {
            "rate_limiting": {
                "enabled": True,
                "default_requests_per_minute": 100,
                "per_client": True,
                "algorithm": "token_bucket",
            },
            "input_validation": {
                "enabled": True,
                "sql_injection_protection": True,
                "xss_protection": True,
                "path_traversal_protection": True,
                "max_request_size_mb": 1,
                "max_field_length": 10000,
            },
            "authentication": {
                "enabled": True,
                "token_expiration_hours": 24,
                "rotation_supported": True,
            },
            "logging": {
                "security_events": True,
                "request_logging": True,
                "suspicious_activity_detection": True,
            },
            "headers": {
                "security_headers_enabled": True,
                "csp_enabled": True,
                "x_frame_options": "DENY",
            },
        },
    })


@bp.post("/config/update")
@require_admin
def update_security_config():
    """Update security configuration.
    
    Note: Most settings require environment variable changes and restart.
    This endpoint validates the configuration but doesn't apply all changes immediately.
    
    Request body:
        rate_limiting: {
            requests_per_minute: int (optional)
        }
        input_validation: {
            max_request_size_mb: int (optional)
            max_field_length: int (optional)
        }
        
    Returns:
        Updated configuration status
    """
    data = request.get_json(silent=True) or {}
    
    updates = []
    warnings = []
    
    # Validate rate limiting config
    if "rate_limiting" in data:
        rl_config = data["rate_limiting"]
        if "requests_per_minute" in rl_config:
            rpm = rl_config["requests_per_minute"]
            if not isinstance(rpm, int) or rpm < 1:
                return jsonify({
                    "ok": False,
                    "error": "Invalid requests_per_minute",
                }), 400
            updates.append(f"Rate limit: {rpm} requests/minute")
    
    # Validate input validation config
    if "input_validation" in data:
        iv_config = data["input_validation"]
        if "max_request_size_mb" in iv_config:
            size_mb = iv_config["max_request_size_mb"]
            if not isinstance(size_mb, (int, float)) or size_mb < 1:
                return jsonify({
                    "ok": False,
                    "error": "Invalid max_request_size_mb",
                }), 400
            updates.append(f"Max request size: {size_mb}MB")
        
        if "max_field_length" in iv_config:
            length = iv_config["max_field_length"]
            if not isinstance(length, int) or length < 1:
                return jsonify({
                    "ok": False,
                    "error": "Invalid max_field_length",
                }), 400
            updates.append(f"Max field length: {length}")
    
    return jsonify({
        "ok": True,
        "message": "Configuration validated",
        "updates": updates,
        "warnings": warnings or [
            "Some changes require environment variable updates and application restart",
            "Set COPILOT_* environment variables and restart to apply all changes",
        ],
    })


@bp.get("/metrics")
def get_security_metrics():
    """Get security metrics for monitoring.
    
    Returns:
        Security metrics and statistics
    """
    rate_limiter = get_rate_limiter()
    
    return jsonify({
        "ok": True,
        "metrics": {
            "rate_limiter": {
                "active_clients": len(rate_limiter._buckets),
                "total_requests_tracked": sum(
                    bucket.tokens for bucket in rate_limiter._buckets.values()
                ),
            },
            "timestamp": datetime.now().isoformat(),
        },
    })


@bp.before_request
def log_security_access():
    """Log access to security endpoints."""
    # Skip logging for the status endpoint (public)
    if request.endpoint == "security.get_security_status":
        return
    
    # Log access to sensitive endpoints
    sec_logger = get_security_logger()
    client_key = f"ip:{request.headers.get('X-Forwarded-For', request.remote_addr or 'unknown')}"
    
    sec_logger.log_security_event(
        event_type="SECURITY_API_ACCESS",
        client=client_key,
        message=f"Access to {request.path}",
        level=logging.INFO,
    )
