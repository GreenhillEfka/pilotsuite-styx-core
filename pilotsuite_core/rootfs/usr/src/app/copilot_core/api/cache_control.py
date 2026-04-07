"""Cache-Control header helpers for GET endpoints.

Usage in a Flask view::

    from copilot_core.api.cache_control import cache, no_cache

    @bp.get("/stats")
    @cache(max_age=30)
    def get_stats():
        ...

    @bp.get("/live")
    @no_cache
    def get_live():
        ...

Available decorators:
    - ``cache(max_age=60)``    — public, stale-while-revalidate
    - ``no_cache``             — no-store, no-cache
    - ``short_lived(max_age)`` — private, shorter TTL
    - ``immutable``            — for versioned assets (hash in URL)
"""

from __future__ import annotations

import functools
import time
from typing import Callable, Optional, Tuple, Union

from flask import make_response, request
from werkzeug.wrappers import Response


def _set_cache_headers(
    response: Response,
    *,
    public: bool,
    max_age: Optional[int],
    no_cache: bool,
    immutable: bool,
) -> Response:
    """Apply cache headers to a Flask/Werkzeug response."""
    if no_cache:
        response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, private"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        return response

    parts = []
    if public:
        parts.append("public")
    else:
        parts.append("private")

    if max_age is not None and max_age > 0:
        parts.append(f"max-age={int(max_age)}")
        parts.append("stale-while-revalidate=30")

    if immutable:
        parts.append("immutable")

    response.headers["Cache-Control"] = ", ".join(parts)
    return response


def cache(
    max_age: int = 60,
    public: bool = True,
) -> Callable:
    """Decorator: add public Cache-Control with ``max-age``.

    Use for rarely-changing data that is safe to share across clients
    and CDNs (e.g. stats, health, entity counts).
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapper(*args, **kwargs) -> Union[Response, Tuple]:
            # Honour If-None-Match / ETag for conditional requests
            # (If the view returns a proper 304 we should honour it)
            response = f(*args, **kwargs)

            if isinstance(response, tuple) and len(response) == 2:
                # unpack (body, status)
                body_or_resp, status = response
                if isinstance(body_or_resp, Response):
                    resp = body_or_resp
                else:
                    resp = make_response(body_or_resp, status)
            elif isinstance(response, Response):
                resp = response
            else:
                resp = make_response(response)

            _set_cache_headers(resp, public=public, max_age=max_age, no_cache=False, immutable=False)
            return resp

        return wrapper
    return decorator


def no_cache(f: Callable) -> Callable:
    """Decorator: disable all caching (no-store).

    Use for authenticated, personalised, or frequently-changing data.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs) -> Union[Response, Tuple]:
        response = f(*args, **kwargs)

        if isinstance(response, tuple) and len(response) == 2:
            body_or_resp, status = response
            if isinstance(body_or_resp, Response):
                resp = body_or_resp
            else:
                resp = make_response(body_or_resp, status)
        elif isinstance(response, Response):
            resp = response
        else:
            resp = make_response(response)

        _set_cache_headers(resp, public=False, max_age=None, no_cache=True, immutable=False)
        return resp

    return wrapper


def short_lived(max_age: int = 10) -> Callable:
    """Decorator: private, short max-age.

    Use for user-specific data that changes frequently.
    """
    def decorator(f: Callable) -> Callable:
        @functools.wraps(f)
        def wrapper(*args, **kwargs) -> Union[Response, Tuple]:
            response = f(*args, **kwargs)

            if isinstance(response, tuple) and len(response) == 2:
                body_or_resp, status = response
                if isinstance(body_or_resp, Response):
                    resp = body_or_resp
                else:
                    resp = make_response(body_or_resp, status)
            elif isinstance(response, Response):
                resp = response
            else:
                resp = make_response(response)

            _set_cache_headers(resp, public=False, max_age=max_age, no_cache=False, immutable=False)
            return resp

        return wrapper
    return decorator


def immutable(f: Callable) -> Callable:
    """Decorator: immutable (for versioned/hash-named assets).

    Use for files whose URL contains a content hash or version number.
    """
    @functools.wraps(f)
    def wrapper(*args, **kwargs) -> Union[Response, Tuple]:
        response = f(*args, **kwargs)

        if isinstance(response, tuple) and len(response) == 2:
            body_or_resp, status = response
            if isinstance(body_or_resp, Response):
                resp = body_or_resp
            else:
                resp = make_response(body_or_resp, status)
        elif isinstance(response, Response):
            resp = response
        else:
            resp = make_response(response)

        _set_cache_headers(resp, public=True, max_age=None, no_cache=False, immutable=True)
        return resp

    return wrapper


def conditional_response(
    data: dict,
    etag: Optional[str] = None,
    last_modified: Optional[float] = None,
    max_age: int = 60,
) -> Tuple:
    """Return 304 Not Modified if client sends matching ETag / If-Modified-Since.

    Call this at the start of a cacheable GET endpoint::

        @bp.get("/stats")
        def get_stats():
            data = _compute_stats()
            return conditional_response(
                data,
                etag=get_etag(),
                last_modified=stat_mtime,
                max_age=30,
            )

    If client cache is fresh, returns (None, 304) — caller should return that.
    Otherwise returns a (data, 200) tuple with cache headers already set.
    """
    from flask import make_response

    # ETag takes priority
    if etag:
        if_none_match = request.headers.get("If-None-Match")
        if if_none_match and if_none_match == etag:
            resp = make_response("", 304)
            resp.headers["Cache-Control"] = f"public, max-age={max_age}"
            return None, 304

    # Last-Modified fallback
    if last_modified:
        if_modified_since = request.headers.get("If-Modified-Since")
        if if_modified_since:
            try:
                from email.utils import parsedate_to_datetime
                client_date = parsedate_to_datetime(if_modified_since)
                if client_date.timestamp() >= last_modified:
                    resp = make_response("", 304)
                    resp.headers["Cache-Control"] = f"public, max-age={max_age}"
                    return None, 304
            except Exception:
                pass

    # Fresh response with cache headers
    resp = make_response(data, 200)
    resp.headers["Cache-Control"] = f"public, max-age={max_age}, stale-while-revalidate=30"
    if etag:
        resp.headers["ETag"] = etag
    if last_modified:
        resp.headers["Last-Modified"] = _http_date(last_modified)

    return data, 200


def _http_date(timestamp: float) -> str:
    """Format a Unix timestamp as an RFC 7231 HTTP date string."""
    from email.utils import formatdate
    return formatdate(timestamp, usegmt=True)
