"""Standardized API error response helpers.

Provides consistent JSON error structure across all API endpoints:

    {
        "ok": False,
        "error": "<error_code>",
        "message": "<human-readable message>",
        "details": {...},          # optional, extra context
        "request_id": "<uuid4>",  # optional, for tracing
    }

HTTP status codes used:
    400  Bad Request        — malformed input
    401  Unauthorized       — auth required or token invalid
    403  Forbidden         — authenticated but not permitted
    404  Not Found          — resource does not exist
    409  Conflict           — state conflict (e.g. duplicate)
    422  Unprocessable      — valid JSON but semantic error
    429  Too Many Requests  — rate limit exceeded (Retry-After header set)
    500  Internal Error     — unexpected server error
"""

from __future__ import annotations

import logging
import time
import uuid
from typing import Any, Dict, Optional, Tuple

from flask import Request, jsonify, make_response, request

logger = logging.getLogger(__name__)

# ── Error code constants ─────────────────────────────────────────────────

ERR_BAD_REQUEST        = "bad_request"
ERR_UNAUTHORIZED       = "unauthorized"
ERR_FORBIDDEN          = "forbidden"
ERR_NOT_FOUND          = "not_found"
ERR_CONFLICT           = "conflict"
ERR_UNPROCESSABLE      = "unprocessable_entity"
ERR_RATE_LIMITED       = "rate_limit_exceeded"
ERR_INTERNAL           = "internal_error"
ERR_SERVICE_UNAVAILABLE = "service_unavailable"
ERR_VALIDATION         = "validation_error"
ERR_NOT_IMPLEMENTED    = "not_implemented"
ERR_METHOD_NOT_ALLOWED = "method_not_allowed"


# ── Core builder ────────────────────────────────────────────────────────

def api_error(
    code: str,
    message: str,
    status: int = 400,
    details: Optional[Dict[str, Any]] = None,
    request_id: Optional[str] = None,
    req: Optional[Request] = None,
) -> Tuple[Any, int]:
    """Build a standardized error response.

    Args:
        code: Short error code string (e.g. "not_found").
        message: Human-readable description.
        status: HTTP status code.
        details: Optional extra payload (validation errors, field-level info).
        request_id: Optional id for request tracing. If omitted, generated
            from the current request headers or a fresh UUID.
        req: Flask request object. When omitted the global ``request`` is used.

    Returns:
        (Flask response, status_code) tuple suitable for returning from a view.
    """
    if request_id is None:
        request_id = _get_request_id(req)

    body: Dict[str, Any] = {
        "ok": False,
        "error": code,
        "message": message,
        "request_id": request_id,
    }
    if details:
        body["details"] = details

    return jsonify(body), status


def _get_request_id(req: Optional[Request] = None) -> str:
    """Extract or generate a request ID for tracing."""
    if req is None:
        try:
            req = request  # noqa: F821 (global request)
        except RuntimeError:
            return str(uuid.uuid4())

    # Prefer explicit header; fall back to a generated ID stored in g
    from flask import g, has_request_context
    if has_request_context():
        rid = getattr(g, "request_id", None)
        if rid:
            return rid
        # Check incoming headers
        for header in ("X-Request-ID", "X-Correlation-ID", "X-Trace-ID"):
            val = req.headers.get(header)
            if val:
                return val
        # Generate and cache for this request
        rid = str(uuid.uuid4())
        g.request_id = rid
        return rid

    return str(uuid.uuid4())


# ── Convenience constructors ──────────────────────────────────────────────

def bad_request(
    message: str = "Bad request",
    details: Optional[Dict[str, Any]] = None,
    req: Optional[Request] = None,
) -> Tuple[Any, int]:
    return api_error(ERR_BAD_REQUEST, message, 400, details, req=req)


def unauthorized(
    message: str = "Authentication required",
    req: Optional[Request] = None,
) -> Tuple[Any, int]:
    return api_error(ERR_UNAUTHORIZED, message, 401, req=req)


def forbidden(
    message: str = "Permission denied",
    req: Optional[Request] = None,
) -> Tuple[Any, int]:
    return api_error(ERR_FORBIDDEN, message, 403, req=req)


def not_found(
    resource: str = "Resource",
    req: Optional[Request] = None,
) -> Tuple[Any, int]:
    return api_error(ERR_NOT_FOUND, f"{resource} not found", 404, req=req)


def conflict(
    message: str = "Resource already exists or state conflict",
    details: Optional[Dict[str, Any]] = None,
    req: Optional[Request] = None,
) -> Tuple[Any, int]:
    return api_error(ERR_CONFLICT, message, 409, details, req=req)


def unprocessable(
    message: str = "Unprocessable entity",
    details: Optional[Dict[str, Any]] = None,
    req: Optional[Request] = None,
) -> Tuple[Any, int]:
    return api_error(ERR_UNPROCESSABLE, message, 422, details, req=req)


def validation_error(
    errors: Dict[str, str],
    message: str = "Validation failed",
    req: Optional[Request] = None,
) -> Tuple[Any, int]:
    """Build a 422 validation error with field-level messages."""
    return api_error(
        ERR_VALIDATION,
        message,
        422,
        details={"fields": errors},
        req=req,
    )


def rate_limited(
    retry_after: int,
    message: str = "Rate limit exceeded",
    req: Optional[Request] = None,
) -> Tuple[Any, int]:
    """Build a 429 response with Retry-After header and structured body."""
    from flask import g, make_response as _make_response

    body, status = api_error(ERR_RATE_LIMITED, message, 429, req=req)
    resp = _make_response(body, status)
    resp.headers["Retry-After"] = str(retry_after)
    resp.headers["X-RateLimit-Reset"] = str(int(time.time()) + retry_after)
    if hasattr(g, "rate_limit_info"):
        info = g.rate_limit_info
        resp.headers["X-RateLimit-Limit"] = str(info.get("limit", ""))
        resp.headers["X-RateLimit-Remaining"] = "0"
    return resp


def service_unavailable(
    message: str = "Service temporarily unavailable",
    details: Optional[Dict[str, Any]] = None,
    req: Optional[Request] = None,
) -> Tuple[Any, int]:
    return api_error(ERR_SERVICE_UNAVAILABLE, message, 503, details, req=req)


def internal_error(
    message: str = "Internal server error",
    log: str = "",
    req: Optional[Request] = None,
) -> Tuple[Any, int]:
    """500 with structured body. Logs the raw error safely."""
    if log:
        logger.exception("API internal error: %s", log)
    else:
        logger.exception("API internal error")
    return api_error(ERR_INTERNAL, message, 500, req=req)


def not_implemented(
    message: str = "Endpoint not implemented",
    req: Optional[Request] = None,
) -> Tuple[Any, int]:
    return api_error(ERR_NOT_IMPLEMENTED, message, 501, req=req)


def method_not_allowed(
    message: str = "Method not allowed",
    req: Optional[Request] = None,
) -> Tuple[Any, int]:
    return api_error(ERR_METHOD_NOT_ALLOWED, message, 405, req=req)


# ── Flask response helper with Cache-Control ────────────────────────────

def success_response(
    data: Dict[str, Any],
    status: int = 200,
    cacheable: bool = False,
    max_age: int = 60,
) -> Tuple[Any, int]:
    """Build a standard success response with optional cache headers.

    Args:
        data: Response body dict. ``ok: True`` is injected if not present.
        status: HTTP status code (default 200).
        cacheable: If True, add Cache-Control: public, max-age=<max_age>.
        max_age: TTL in seconds for cacheable responses.
    """
    body = dict(data)
    body.setdefault("ok", True)

    resp = jsonify(body), status

    if cacheable and max_age > 0:
        _resp = make_response(resp[0], resp[1])
        _resp.headers["Cache-Control"] = f"public, max-age={max_age}"
        return _resp, status

    return resp
