"""API Gateway with Rate Limiting (Slice 148).

Centralized API management:
- Request routing
- Rate limiting per client
- Authentication middleware
- Response caching
"""

from __future__ import annotations

import functools
import logging
import time
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Set
from collections import defaultdict
from flask import request, jsonify, g

_LOGGER = logging.getLogger(__name__)


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    requests_per_minute: int = 60
    burst_size: int = 10
    block_duration_seconds: float = 60.0


class RateLimiter:
    """Token bucket rate limiter per client."""
    
    def __init__(self, config: RateLimitConfig = None):
        self._config = config or RateLimitConfig()
        self._buckets: Dict[str, Dict[str, Any]] = defaultdict(
            lambda: {"tokens": self._config.burst_size, "last_update": time.monotonic(), "blocked_until": 0}
        )
    
    def _get_client_id(self) -> str:
        """Extract client identifier."""
        # Try API key first, then IP
        api_key = request.headers.get("X-API-Key", "").strip()
        if api_key:
            return f"key:{api_key[:16]}"
        return f"ip:{request.remote_addr or 'unknown'}"
    
    def is_allowed(self) -> tuple[bool, Optional[Dict[str, Any]]]:
        """Check if request is allowed."""
        client_id = self._get_client_id()
        now = time.monotonic()
        bucket = self._buckets[client_id]
        
        # Check if blocked
        if bucket["blocked_until"] > now:
            retry_after = int(bucket["blocked_until"] - now)
            return False, {"error": "Rate limit exceeded", "retry_after": retry_after}
        
        # Add tokens based on time passed
        time_passed = now - bucket["last_update"]
        tokens_to_add = time_passed * (self._config.requests_per_minute / 60.0)
        bucket["tokens"] = min(bucket["tokens"] + tokens_to_add, self._config.burst_size)
        bucket["last_update"] = now
        
        # Check if request can be made
        if bucket["tokens"] >= 1:
            bucket["tokens"] -= 1
            return True, None
        else:
            # Block client
            bucket["blocked_until"] = now + self._config.block_duration_seconds
            return False, {"error": "Rate limit exceeded", "retry_after": int(self._config.block_duration_seconds)}


class APIGateway:
    """Centralized API gateway."""
    
    def __init__(self):
        self._rate_limiter = RateLimiter()
        self._routes: Dict[str, Dict[str, Any]] = {}
        self._middleware: List[Callable] = []
        self._cache: Dict[str, tuple[Any, float]] = {}
        self._cache_ttl = 60.0
    
    def rate_limit(self, config: RateLimitConfig = None):
        """Decorator to apply rate limiting."""
        limiter = RateLimiter(config)
        
        def decorator(f: Callable) -> Callable:
            @functools.wraps(f)
            def wrapper(*args, **kwargs):
                allowed, error = limiter.is_allowed()
                if not allowed:
                    return jsonify(error), 429
                return f(*args, **kwargs)
            return wrapper
        return decorator
    
    def require_auth(self, f: Callable) -> Callable:
        """Decorator to require authentication."""
        @functools.wraps(f)
        def wrapper(*args, **kwargs):
            from copilot_core.api.security import validate_token
            if not validate_token(request):
                return jsonify({"error": "Authentication required"}), 401
            g.authenticated = True
            return f(*args, **kwargs)
        return wrapper
    
    def cached(self, ttl_seconds: float = 60.0):
        """Decorator to cache responses."""
        def decorator(f: Callable) -> Callable:
            @functools.wraps(f)
            def wrapper(*args, **kwargs):
                cache_key = f"{f.__name__}:{str(request.view_args)}:{str(request.args)}"
                now = time.monotonic()
                
                # Check cache
                if cache_key in self._cache:
                    result, timestamp = self._cache[cache_key]
                    if now - timestamp < ttl_seconds:
                        return result
                
                # Execute and cache
                result = f(*args, **kwargs)
                self._cache[cache_key] = (result, now)
                
                # Cleanup old cache entries periodically
                if len(self._cache) > 1000:
                    self._cleanup_cache()
                
                return result
            return wrapper
        return decorator
    
    def _cleanup_cache(self):
        """Remove expired cache entries."""
        now = time.monotonic()
        expired = [k for k, (v, t) in self._cache.items() if now - t > self._cache_ttl]
        for k in expired:
            del self._cache[k]


# Global gateway instance
gateway = APIGateway()


def init_gateway(app):
    """Initialize gateway with Flask app."""
    @app.before_request
    def check_rate_limit():
        # Apply global rate limiting
        allowed, error = gateway._rate_limiter.is_allowed()
        if not allowed:
            return jsonify(error), 429
    
    _LOGGER.info("API Gateway initialized")
