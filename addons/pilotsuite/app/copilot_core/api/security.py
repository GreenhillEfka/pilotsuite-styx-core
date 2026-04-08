"""Shared authentication helpers for API blueprints."""
from __future__ import annotations

import hmac
import json
import os
import time
from functools import wraps
from typing import Any, Callable

from flask import g, request as flask_request, jsonify

OPTIONS_PATH = "/data/options.json"

# Token cache: (token_value, timestamp)
_token_cache: tuple[str, float] = ("", 0.0)
_TOKEN_CACHE_TTL = 60.0  # seconds


def get_auth_token(options_path: str = OPTIONS_PATH) -> str:
    """Return the configured shared token, if any.

    Uses a 60-second TTL cache to avoid disk reads on every request.
    """
    global _token_cache

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
    
    Returns True if token is valid or authentication is disabled.
    Returns False if token is required but invalid.
    """

    # Check if auth is required
    if not is_auth_required():
        # Auth disabled - allow all requests
        return True
    
    # Auth required - validate token
    token = get_auth_token()
    if not token:
        # No token configured - allow all requests (first-run / unconfigured)
        return True

    header_token = (request.headers.get("X-Auth-Token") or "").strip()
    if header_token and hmac.compare_digest(header_token, token):
        return True

    auth_header = (request.headers.get("Authorization") or "").strip()
    if auth_header.startswith("Bearer "):
        candidate = auth_header.split(" ", 1)[1].strip()
        if candidate and hmac.compare_digest(candidate, token):
            return True

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
