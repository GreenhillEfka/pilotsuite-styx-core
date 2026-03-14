"""Shared authentication helpers for API blueprints."""
from __future__ import annotations

import hmac
import json
import logging
import os
import secrets
import threading
import time
from functools import wraps
from typing import Any, Callable

from flask import g, request as flask_request, jsonify

_LOGGER = logging.getLogger(__name__)

OPTIONS_PATH = "/data/options.json"
AUTO_TOKEN_PATH = "/data/.pilotsuite_token"

# Token cache: (token_value, timestamp) — protected by _token_lock
_token_cache: tuple[str, float] = ("", 0.0)
_token_lock = threading.Lock()
_TOKEN_CACHE_TTL = 60.0  # seconds


def _ensure_auto_token() -> str:
    """Generate and persist an auto-token if none exists (1-Key-Flow).

    On first startup with no configured auth_token, a random token is
    generated and saved to AUTO_TOKEN_PATH. Subsequent starts reuse it.
    """
    try:
        with open(AUTO_TOKEN_PATH, "r", encoding="utf-8") as fh:
            token = fh.read().strip()
        if token:
            return token
    except FileNotFoundError:
        pass
    except Exception:
        _LOGGER.debug("Could not read auto-token file, generating new one")

    token = secrets.token_urlsafe(32)
    try:
        with open(AUTO_TOKEN_PATH, "w", encoding="utf-8") as fh:
            fh.write(token)
        _LOGGER.info("Auto-generated API token (1-Key-Flow): %s...%s", token[:8], token[-4:])
    except Exception:
        _LOGGER.warning("Could not persist auto-token to %s", AUTO_TOKEN_PATH)
    return token


def get_auth_token(options_path: str = OPTIONS_PATH) -> str:
    """Return the active auth token.

    Priority: env var > options.json > auto-generated (1-Key-Flow).
    Uses a 60-second TTL cache to avoid disk reads on every request.
    Thread-safe via double-checked locking.
    """
    global _token_cache

    # Fast path (no lock): check if cache is still valid
    now = time.monotonic()
    cached_token, cached_at = _token_cache
    if cached_token and (now - cached_at) < _TOKEN_CACHE_TTL:
        return cached_token

    # Slow path: acquire lock, re-check, then refresh
    with _token_lock:
        now = time.monotonic()
        cached_token, cached_at = _token_cache
        if cached_token and (now - cached_at) < _TOKEN_CACHE_TTL:
            return cached_token

        token = os.environ.get("COPILOT_AUTH_TOKEN", "").strip()
        if not token:
            try:
                with open(options_path, "r", encoding="utf-8") as fh:
                    opts: Any = json.load(fh) or {}
                token = str(opts.get("auth_token", "")).strip()
            except Exception:
                token = ""

        # 1-Key-Flow: auto-generate token if nothing is configured
        if not token:
            token = _ensure_auto_token()

        _token_cache = (token, now)
        return token


def is_auth_required(options_path: str = OPTIONS_PATH) -> bool:
    """Check if authentication is required.

    Returns True by default (secure default).
    Can be disabled via:
    - Environment: COPILOT_AUTH_REQUIRED=false
    - Options: auth_required: false
    """
    # Check environment variable first (highest priority)
    env_value = os.environ.get("COPILOT_AUTH_REQUIRED", "").lower().strip()
    if env_value == "false":
        return False
    if env_value == "true":
        return True

    # Check options.json
    try:
        with open(options_path, "r", encoding="utf-8") as fh:
            opts: Any = json.load(fh) or {}
        if opts.get("auth_required") is False:
            return False
    except Exception:
        pass

    # Default: require authentication (secure by default)
    return True


def validate_token(request) -> bool:
    """Validate the shared token against the incoming request.

    Returns True when authentication is disabled or a valid token is provided.
    Returns False when authentication is required and token validation fails.
    """

    # Check if auth is required
    if not is_auth_required():
        # Auth disabled - allow all requests
        return True

    # Auth required - validate token (always has a token via 1-Key-Flow)
    token = get_auth_token()

    header_token = (request.headers.get("X-Auth-Token") or "").strip()
    if header_token and hmac.compare_digest(header_token, token):
        return True

    auth_header = (request.headers.get("Authorization") or "").strip()
    if auth_header.startswith("Bearer "):
        candidate = auth_header.split(" ", 1)[1].strip()
        if candidate and hmac.compare_digest(candidate, token):
            return True

    # Log failed authentication attempt
    _LOGGER.warning(
        "Failed authentication attempt from %s (path=%s, method=%s)",
        request.remote_addr or "unknown",
        request.path or "unknown",
        request.method or "unknown"
    )
    return False


def require_token(f: Callable) -> Callable:
    """Decorator to require valid token for an endpoint."""
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if not validate_token(flask_request):
            return jsonify({
                "ok": False,
                "error": "Authentication required",
                "message": "Valid X-Auth-Token header or Bearer token required"
            }), 401
        return f(*args, **kwargs)
    return decorated_function


def optional_token(f: Callable) -> Callable:
    """Decorator for endpoints that work with or without token.

    Sets ``flask.g.token_valid`` so the handler can branch on auth status.
    """
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        g.token_valid = validate_token(flask_request)
        return f(*args, **kwargs)
    return decorated_function


# Alias for backward compatibility
require_api_key = require_token


def get_token_source(options_path: str = OPTIONS_PATH) -> str:
    """Return the source of the active auth token.

    Returns one of: "env", "options", "auto", "none".
    """
    if os.environ.get("COPILOT_AUTH_TOKEN", "").strip():
        return "env"
    try:
        with open(options_path, "r", encoding="utf-8") as fh:
            opts: Any = json.load(fh) or {}
        if str(opts.get("auth_token", "")).strip():
            return "options"
    except Exception:
        pass
    try:
        with open(AUTO_TOKEN_PATH, "r", encoding="utf-8") as fh:
            if fh.read().strip():
                return "auto"
    except Exception:
        pass
    return "none"


def validate_websocket_token(request) -> bool:
    """Validate token for WebSocket connections.

    Checks (in order):
    1. Query parameter ``?token=xxx``
    2. ``X-Auth-Token`` header

    Returns True when the token is valid.
    Returns False when no token is configured or token doesn't match.
    """
    token = get_auth_token()
    if not token:
        return False

    # 1. Query parameter
    query_token = ""
    if hasattr(request, "args"):
        query_token = (request.args.get("token") or "").strip()
    if query_token and hmac.compare_digest(query_token, token):
        return True

    # 2. X-Auth-Token header
    header_token = ""
    if hasattr(request, "headers"):
        header_token = (request.headers.get("X-Auth-Token") or "").strip()
    if header_token and hmac.compare_digest(header_token, token):
        return True

    return False


def require_admin_token(request) -> bool:
    """Validate that a valid admin token is present.
    
    Unlike validate_token(), this ALWAYS requires a token,
    even if auth is disabled globally (for sensitive operations).
    
    Returns True if a valid token is provided.
    Returns False if no token or invalid token.
    """
    token = get_auth_token()
    if not token:
        # No token configured at all - cannot validate
        return False

    header_token = (request.headers.get("X-Auth-Token") or "").strip()
    if header_token and hmac.compare_digest(header_token, token):
        return True

    auth_header = (request.headers.get("Authorization") or "").strip()
    if auth_header.startswith("Bearer "):
        candidate = auth_header.split(" ", 1)[1].strip()
        if candidate and hmac.compare_digest(candidate, token):
            return True

    return False


def require_admin(f: Callable) -> Callable:
    """Decorator to require valid admin token for sensitive operations.
    
    Unlike require_token, this ALWAYS requires authentication,
    even if auth is disabled globally.
    """
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if not require_admin_token(flask_request):
            return jsonify({
                "ok": False,
                "error": "Admin authentication required",
                "message": "Valid X-Auth-Token header or Bearer token required for this operation"
            }), 403
        return f(*args, **kwargs)
    return decorated_function
