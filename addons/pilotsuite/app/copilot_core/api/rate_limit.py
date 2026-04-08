"""Rate Limiting for API endpoints."""

from __future__ import annotations

import time
import os
from collections import defaultdict
from threading import Lock
from typing import Any, Callable, Dict, Optional
from functools import wraps

from flask import jsonify, request


class RateLimiter:
    """Simple in-memory rate limiter."""
    
    def __init__(
        self,
        default_limits: Dict[str, int] | None = None,
        default_period: int = 60,
    ):
        """Initialize rate limiter.
        
        Args:
            default_limits: Dict of endpoint -> requests per period
            default_period: Time period in seconds (default 60 = 1 minute)
        """
        self._limits = default_limits or {}
        self._period = default_period
        self._requests: Dict[str, list] = defaultdict(list)
        self._lock = Lock()
        
    def set_limit(self, endpoint: str, requests: int, period: int | None = None) -> None:
        """Set rate limit for an endpoint."""
        self._limits[endpoint] = requests
        if period:
            self._period = period
    
    def get_limit(self, endpoint: str) -> tuple[int, int]:
        """Get (requests, period) for an endpoint."""
        return self._limits.get(endpoint, (100, 60))  # Default: 100 req/min
    
    def is_allowed(self, key: str, endpoint: str) -> tuple[bool, Dict[str, Any]]:
        """Check if request is allowed.
        
        Returns:
            (allowed: bool, info: dict with remaining, reset_time)
        """
        requests, period = self.get_limit(endpoint)
        
        now = time.time()
        cutoff = now - period
        
        with self._lock:
            # Clean old requests
            self._requests[key] = [
                ts for ts in self._requests[key] if ts > cutoff
            ]
            
            # Check limit
            current_count = len(self._requests[key])
            
            if current_count >= requests:
                # Calculate reset time
                oldest = min(self._requests[key]) if self._requests[key] else now
                reset_time = oldest + period
                
                return False, {
                    "remaining": 0,
                    "reset": int(reset_time),
                    "limit": requests,
                    "period": period,
                }
            
            # Allow request
            self._requests[key].append(now)
            
            return True, {
                "remaining": requests - current_count - 1,
                "reset": int(now + period),
                "limit": requests,
                "period": period,
            }
    
    def reset(self, key: str | None = None) -> None:
        """Reset rate limit for a key or all keys."""
        with self._lock:
            if key:
                self._requests.pop(key, None)
            else:
                self._requests.clear()


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        # Default limits
        _rate_limiter = RateLimiter(
            default_limits={
                "/api/v1/events": 200,
                "/api/v1/habitus": 100,
                "/api/v1/mood": 50,
                "/api/v1/graph": 50,
                "/api/v1/tags": 100,
                "/api/v1/search": 30,
                "/api/v1/notifications": 50,
                "/api/v1/hints": 20,
            },
            default_period=60,
        )
        
        # Allow override via environment
        for endpoint in ["/events", "/habitus", "/mood", "/graph", "/tags", "/search", "/notifications", "/hints"]:
            env_key = f"COPILOT_RATE_LIMIT_{endpoint.replace('/', '').upper()}"
            env_value = os.environ.get(env_key)
            if env_value:
                try:
                    limit = int(env_value)
                    _rate_limiter.set_limit(f"/api/v1{endpoint}", limit)
                except ValueError:
                    pass
    
    return _rate_limiter


def rate_limit(
    endpoint: str | None = None,
    requests: int | None = None,
    period: int | None = None,
) -> Callable:
    """Decorator to apply rate limiting to an endpoint.
    
    Args:
        endpoint: Override endpoint path (default: use request.path)
        requests: Override requests per period
        period: Override period in seconds
    """
    def decorator(f: Callable) -> Callable:
        @wraps(f)
        def decorated_function(*args: Any, **kwargs: Any) -> Any:
            limiter = get_rate_limiter()
            
            # Determine endpoint
            ep = endpoint
            if not ep:
                # Try to get from request
                try:
                    ep = request.path
                except RuntimeError:
                    ep = "/api/v1/default"
            
            # Get client key (IP or token)
            client_ip = request.headers.get("X-Forwarded-For", request.remote_addr)
            token = request.headers.get("X-Auth-Token", "")
            key = f"{client_ip}:{token[:8]}" if token else client_ip
            
            # Check rate limit
            allowed, info = limiter.is_allowed(key, ep)
            
            if not allowed:
                return jsonify({
                    "ok": False,
                    "error": "Rate limit exceeded",
                    "message": f"Too many requests to {ep}",
                    "rate_limit": info,
                }), 429
            
            # Add rate limit headers
            try:
                from flask import make_response
                response = make_response(f(*args, **kwargs))
                response.headers["X-RateLimit-Limit"] = str(info["limit"])
                response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
                response.headers["X-RateLimit-Reset"] = str(info["reset"])
                return response
            except RuntimeError:
                # Outside request context
                return f(*args, **kwargs)
        
        return decorated_function
    return decorator


def get_rate_limit_status() -> Dict[str, Any]:
    """Get rate limiter status for monitoring."""
    limiter = get_rate_limiter()
    return {
        "endpoints": {
            ep: {"requests": reqs, "period": limiter._period}
            for ep, reqs in limiter._limits.items()
        },
        "active_keys": len(limiter._requests),
    }
EOF