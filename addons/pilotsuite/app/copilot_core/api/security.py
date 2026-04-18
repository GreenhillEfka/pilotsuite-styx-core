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

from flask import g, request, jsonify

# NOTE: Do NOT assign flask.request at module level (it causes test pollution).
# Always use flask.request inside request handlers or test_request_context blocks.
_request = request

_LOGGER = logging.getLogger(__name__)

OPTIONS_PATH = "/data/options.json"
AUTO_TOKEN_PATH = "/data/.pilotsuite_token"

# Token cache: (token_value, timestamp) — protected by _token_lock
_token_cache: tuple[str, float] = ("", 0.0)
_token_lock = threading.Lock()
_TOKEN_CACHE_TTL = 60.0  # seconds

# HA user token validation cache: {token_hash: expiry_monotonic}
_ha_token_cache: dict[str, float] = {}
_ha_token_lock = threading.Lock()
_HA_TOKEN_CACHE_TTL = 300.0  # 5 minutes

# Auth-required cache: (result, timestamp) — protected by _auth_lock
_auth_required_cache: tuple[bool, float] = (True, 0.0)
_auth_lock = threading.Lock()
_AUTH_CACHE_TTL = 30.0  # seconds

# Token age enforcement (GAP-5)
_TOKEN_MAX_AGE_SECS = 90 * 86400   # 90 days default
_TOKEN_WARN_AGE_SECS = 70 * 86400  # warn after 70 days


def _ensure_auto_token() -> str:
    """Generate and persist an auto-token if none exists (1-Key-Flow).

    On first startup with no configured auth_token, a random token is
    generated and saved to AUTO_TOKEN_PATH. Subsequent starts reuse it.
    Auto-token file format: {token}\n{created_at_unix}
    """
    try:
        with open(AUTO_TOKEN_PATH, "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        if lines:
            token = lines[0].strip()
            if token:
                return token
    except FileNotFoundError:
        pass
    except Exception:
        _LOGGER.debug("Could not read auto-token file, generating new one")

    token = secrets.token_urlsafe(32)
    created_at = int(time.time())
    try:
        with open(AUTO_TOKEN_PATH, "w", encoding="utf-8") as fh:
            fh.write(f"{token}\n{created_at}\n")
        _LOGGER.info("Auto-generated API token (1-Key-Flow): %s...%s age=0", token[:8], token[-4:])
    except Exception:
        _LOGGER.warning("Could not persist auto-token to %s", AUTO_TOKEN_PATH)
    return token


def _get_token_age() -> float | None:
    """Return age of the auto-generated token in seconds, or None if not an auto-token."""
    try:
        with open(AUTO_TOKEN_PATH, "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        if len(lines) >= 2:
            return time.time() - float(lines[1])
    except Exception:
        pass
    return None


def get_auth_token(options_path: str = OPTIONS_PATH) -> str:
    """Return the active auth token.

    Priority: env var > options.json > auto-generated (1-Key-Flow).
    Uses a 60-second TTL cache to avoid disk reads on every request.
    Thread-safe via double-checked locking.
    """
    global _token_cache

    # Environment overrides must win immediately, even within the TTL window.
    env_token = os.environ.get("COPILOT_AUTH_TOKEN", "").strip()
    if env_token:
        now = time.monotonic()
        if _token_cache != (env_token, _token_cache[1]):
            _token_cache = (env_token, now)
        return env_token

    # Fast path (no lock): check if cache is still valid
    now = time.monotonic()
    cached_token, cached_at = _token_cache
    if cached_token and (now - cached_at) < _TOKEN_CACHE_TTL:
        return cached_token

    # Slow path: acquire lock, re-check, then refresh
    with _token_lock:
        env_token = os.environ.get("COPILOT_AUTH_TOKEN", "").strip()
        now = time.monotonic()
        if env_token:
            _token_cache = (env_token, now)
            return env_token

        cached_token, cached_at = _token_cache
        if cached_token and (now - cached_at) < _TOKEN_CACHE_TTL:
            return cached_token

        token = ""
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
    Uses a 30-second TTL cache to avoid repeated disk reads.
    Can be disabled via:
    - Environment: COPILOT_AUTH_REQUIRED=false
    - Options: auth_required: false
    """
    global _auth_required_cache

    # Environment overrides must win immediately, even within the TTL window.
    env_value = os.environ.get("COPILOT_AUTH_REQUIRED", "").lower().strip()
    if env_value == "false":
        now = time.monotonic()
        _auth_required_cache = (False, now)
        return False
    if env_value == "true":
        now = time.monotonic()
        _auth_required_cache = (True, now)
        return True

    # Fast path (no lock): check if cache is still valid
    now = time.monotonic()
    cached_result, cached_at = _auth_required_cache
    if now - cached_at < _AUTH_CACHE_TTL:
        return cached_result

    # Slow path: acquire lock, re-check, then recompute
    with _auth_lock:
        env_value = os.environ.get("COPILOT_AUTH_REQUIRED", "").lower().strip()
        now = time.monotonic()
        if env_value == "false":
            _auth_required_cache = (False, now)
            return False
        if env_value == "true":
            _auth_required_cache = (True, now)
            return True

        cached_result, cached_at = _auth_required_cache
        if now - cached_at < _AUTH_CACHE_TTL:
            return cached_result

        result = True
        try:
            with open(options_path, "r", encoding="utf-8") as fh:
                opts: Any = json.load(fh) or {}
            if opts.get("auth_required") is False:
                result = False
        except Exception:
            pass

        _auth_required_cache = (result, now)
        return result


def _validate_ha_user_token(candidate: str) -> bool:
    """Check if *candidate* is a valid HA user token (short- or long-lived).

    Validates by calling the HA Core API via the internal Docker network.
    Results are cached for 5 minutes to avoid per-request latency.
    """
    if not candidate or len(candidate) < 20:
        return False

    # Use a hash as cache key (avoid storing full tokens in memory)
    import hashlib
    token_key = hashlib.sha256(candidate.encode()).hexdigest()[:16]

    now = time.monotonic()
    with _ha_token_lock:
        expiry = _ha_token_cache.get(token_key)
        if expiry is not None and now < expiry:
            return True

    # Validate against HA Core API
    # Inside an add-on container: http://supervisor/core/api proxies to HA
    # Direct access: http://homeassistant:8123/api
    ha_urls = [
        os.environ.get("SUPERVISOR_API", "http://supervisor/core/api"),
        "http://homeassistant:8123/api",
    ]

    for base_url in ha_urls:
        try:
            import requests as _req
            resp = _req.get(
                base_url + ("/" if not base_url.endswith("/") else ""),
                headers={"Authorization": f"Bearer {candidate}"},
                timeout=3,
            )
            if resp.status_code == 200:
                with _ha_token_lock:
                    _ha_token_cache[token_key] = now + _HA_TOKEN_CACHE_TTL
                    # Prune expired entries
                    expired = [k for k, v in _ha_token_cache.items() if v < now]
                    for k in expired:
                        del _ha_token_cache[k]
                _LOGGER.debug("Accepted HA user token for %s", base_url)
                return True
        except Exception:
            continue

    return False



def _record_auth_success(request) -> None:
    """Reset brute-force counters on successful auth (best-effort)."""
    try:
        from copilot_core.security.brute_force_protection import record_auth_success as _ras
        _ras()
    except Exception:
        pass

def _record_auth_failure(request) -> None:
    """Record failed auth attempt for brute-force tracking (best-effort)."""
    try:
        from copilot_core.security.brute_force_protection import record_auth_failure as _raf
        _raf()
    except Exception:
        pass

def validate_token(request) -> bool:
    """Validate the shared token against the incoming request.

    Returns True when authentication is disabled or a valid token is provided.
    Returns False when authentication is required and token validation fails.


    Accepts:
    1. Core's own auth token (X-Auth-Token header or Bearer)
    2. HA Ingress requests (X-Ingress-Path header present)
    3. Valid HA user tokens (validated against HA API, cached)
    4. Brute-force tracking on failure / reset on success
    """

    # Check if auth is required
    if not is_auth_required():
        # Auth disabled - allow all requests
        return True

    # Auth required - validate token (always has a token via 1-Key-Flow)
    token = get_auth_token()

    # GAP-5: Check auto-token age
    token_age = _get_token_age()
    if token_age is not None:
        max_age = float(os.environ.get("COPILOT_TOKEN_MAX_AGE_DAYS", "90")) * 86400
        warn_age = float(os.environ.get("COPILOT_TOKEN_WARN_AGE_DAYS", "70")) * 86400
        if token_age > max_age:
            _LOGGER.error(
                "Auto-token expired (age=%.0f days). Set COPILOT_TOKEN_MAX_AGE_DAYS or rotate.",
                token_age / 86400
            )
            return False
        if token_age > warn_age:
            _LOGGER.warning(
                "Auto-token approaching max age (%.0f/%.0f days). Consider rotating.",
                token_age / 86400, max_age / 86400
            )

    header_token = (request.headers.get("X-Auth-Token") or "").strip()
    if header_token and hmac.compare_digest(header_token, token):
        _record_auth_success(request)
        return True

    auth_header = (request.headers.get("Authorization") or "").strip()
    if auth_header.startswith("Bearer "):
        candidate = auth_header.split(" ", 1)[1].strip()
        if candidate and hmac.compare_digest(candidate, token):
            _record_auth_success(request)
            return True

    # Trust requests coming through HA Ingress proxy (user already
    # authenticated by HA at the Ingress gateway).
    if request.headers.get("X-Ingress-Path"):
        return True

    # Fallback: check if the token is a valid HA user token
    # (covers styx-chat-card sending HA frontend access_token)
    if header_token and _validate_ha_user_token(header_token):
        _record_auth_success(request)
        return True
    if auth_header.startswith("Bearer "):
        candidate = auth_header.split(" ", 1)[1].strip()
        if candidate and _validate_ha_user_token(candidate):
            _record_auth_success(request)
            return True

    _record_auth_failure(request)
    # Log failed authentication attempt
    _LOGGER.warning(
        "Failed authentication attempt from %s (path=%s, method=%s)",
        request.remote_addr or "unknown",
        request.path or "unknown",
        request.method or "unknown"
    )
    return False


def require_token(f: Callable | None = None, *, scopes: tuple[str, ...] | None = None) -> Callable:
    """Decorator to require valid token for an endpoint.

    Usage:
        @require_token                      # any valid token
        @require_token(scopes=("read",))   # token must have "read" scope
        @require_token(scopes=("admin", "write"))
    """
    def decorator(ff: Callable) -> Callable:
        @wraps(ff)
        def decorated(*args: Any, **kwargs: Any) -> Any:
            # Use ``is True`` (not ``not``) to survive sys.modules mocking
            # (MagicMock.__bool__ returns True causing false positives)
            if validate_token(request) is not True:
                return jsonify({
                    "ok": False,
                    "error": "Authentication required",
                    "message": "Valid X-Auth-Token header or Bearer token required"
                }), 401

            # Scope check (GAP-1: token scope enforcement)
            if scopes is not None:
                token_scopes = getattr(g, "token_scopes", None)
                if not token_scopes or not any(s in token_scopes for s in scopes):
                    return jsonify({
                        "ok": False,
                        "error": "Insufficient scope",
                        "message": f"Token requires one of: {', '.join(scopes)}"
                    }), 403

            return ff(*args, **kwargs)
        return decorated

    if f is not None:
        return decorator(f)
    return decorator

def require_scope(*rScopes: str) -> Callable:
    """Decorator: require specific token scopes on an already-authenticated endpoint."""
    def decorator(ff: Callable) -> Callable:
        @wraps(ff)
        def decorated(*args: Any, **kwargs: Any) -> Any:
            # Use ``is not True`` to survive sys.modules mocking
            if getattr(g, "token_valid", False) is not True:
                return jsonify({
                    "ok": False,
                    "error": "Authentication required",
                    "message": "Valid token required before scope check"
                }), 401
            token_scopes = getattr(g, "token_scopes", None)
            if not token_scopes or not any(s in token_scopes for s in rScopes):
                return jsonify({
                    "ok": False,
                    "error": "Insufficient scope",
                    "message": f"Token requires one of: {', '.join(rScopes)}"
                }), 403
            return ff(*args, **kwargs)
        return decorated
    return decorator


def optional_token(f: Callable) -> Callable:
    """Decorator for endpoints that work with or without token.

    Sets ``flask.g.token_valid`` so the handler can branch on auth status.
    """
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        g.token_valid = validate_token(request)
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

    GAP-4 fix: Requires 'admin' scope on the token, OR
    allows any valid token when auth is globally disabled.

    Unlike validate_token(), this ALWAYS requires a token,
    even if auth is disabled globally (for sensitive operations).
    Returns True if a valid token is provided and has admin scope
    (or auth is disabled and a valid token is present).
    """
    token = get_auth_token()
    if not token:
        return False

    header_token = (request.headers.get("X-Auth-Token") or "").strip()
    if header_token and hmac.compare_digest(header_token, token):
        if not is_auth_required():
            return True
        token_scopes = getattr(g, "token_scopes", None)
        if token_scopes and "admin" in token_scopes:
            return True
        return False

    auth_header = (request.headers.get("Authorization") or "").strip()
    if auth_header.startswith("Bearer "):
        candidate = auth_header.split(" ", 1)[1].strip()
        if candidate and hmac.compare_digest(candidate, token):
            if not is_auth_required():
                return True
            token_scopes = getattr(g, "token_scopes", None)
            if token_scopes and "admin" in token_scopes:
                return True
            return False

    return False


def require_admin(f: Callable) -> Callable:
    """Decorator to require valid admin token for sensitive operations.

    GAP-4 fix: Now checks for 'admin' scope on the validated token.
    Unlike require_token, this ALWAYS requires authentication,
    even if auth is disabled globally.
    """
    @wraps(f)
    def decorated_function(*args: Any, **kwargs: Any) -> Any:
        if not require_admin_token(request):
            return jsonify({
                "ok": False,
                "error": "Admin authentication required",
                "message": "Valid X-Auth-Token header or Bearer token required for this operation"
            }), 403
        return f(*args, **kwargs)
    return decorated_function
