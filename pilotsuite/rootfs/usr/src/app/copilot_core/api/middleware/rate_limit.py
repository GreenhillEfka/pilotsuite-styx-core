"""
Rate Limiting Middleware

Token Bucket Algorithm implementation for API rate limiting.

Features:
- Per-API-Key limits (configurable)
- Default: 100 requests/min, burst: 20
- Headers: X-RateLimit-Limit, X-RateLimit-Remaining, X-RateLimit-Reset
- 429 Response with Retry-After on limit exceeded
"""

from __future__ import annotations

import logging
import threading
import time
from typing import Optional, Dict, Callable
from functools import wraps

from flask import request, jsonify, Response, g

from copilot_core.models.rate_limit import (
    RateLimitConfig,
    TokenBucket,
    RateLimitHeaders,
    DEFAULT_RATE_LIMIT_CONFIG,
)

logger = logging.getLogger(__name__)


class RateLimitStore:
    """
    Thread-safe store for token buckets.
    
    Stores buckets per client identifier (API key or IP).
    """
    
    def __init__(self):
        self._buckets: Dict[str, TokenBucket] = {}
        self._configs: Dict[str, RateLimitConfig] = {}
        self._lock = threading.RLock()
    
    def get_bucket(self, client_id: str, config: RateLimitConfig) -> TokenBucket:
        """Get or create a token bucket for a client."""
        with self._lock:
            if client_id not in self._buckets:
                self._buckets[client_id] = TokenBucket.from_config(config)
                self._configs[client_id] = config
            return self._buckets[client_id]
    
    def update_config(self, client_id: str, config: RateLimitConfig) -> None:
        """Update config for a client (creates new bucket)."""
        with self._lock:
            self._configs[client_id] = config
            self._buckets[client_id] = TokenBucket.from_config(config)
    
    def get_config(self, client_id: str) -> Optional[RateLimitConfig]:
        """Get config for a client."""
        with self._lock:
            return self._configs.get(client_id)
    
    def remove_client(self, client_id: str) -> None:
        """Remove a client's bucket and config."""
        with self._lock:
            self._buckets.pop(client_id, None)
            self._configs.pop(client_id, None)
    
    def get_all_status(self) -> Dict[str, dict]:
        """Get status for all clients."""
        with self._lock:
            return {
                client_id: {
                    "config": config.to_dict(),
                    "bucket": self._buckets[client_id].to_dict(),
                }
                for client_id, config in self._configs.items()
            }
    
    def cleanup_stale(self, max_age_seconds: int = 3600) -> int:
        """Remove buckets inactive for more than max_age_seconds."""
        now = time.time()
        removed = 0
        with self._lock:
            stale_clients = [
                client_id
                for client_id, bucket in self._buckets.items()
                if now - bucket.last_refill > max_age_seconds
            ]
            for client_id in stale_clients:
                self.remove_client(client_id)
                removed += 1
        return removed


# Global rate limit store
_rate_limit_store = RateLimitStore()


def get_rate_limit_store() -> RateLimitStore:
    """Get the global rate limit store."""
    return _rate_limit_store


def extract_client_id() -> str:
    """
    Extract client identifier from request.
    
    Priority:
    1. X-API-Key header
    2. Authorization Bearer token
    3. X-Forwarded-For header (first IP)
    4. Remote address
    """
    # Check API key
    api_key = request.headers.get("X-API-Key")
    if api_key:
        return f"apikey:{api_key}"
    
    # Check Bearer token
    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
        return f"token:{token}"
    
    # Check forwarded IP
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        # First IP in chain is the client
        client_ip = forwarded.split(",")[0].strip()
        return f"ip:{client_ip}"
    
    # Fallback to remote address
    return f"ip:{request.remote_addr or 'unknown'}"


def rate_limit_exceeded_response(
    config: RateLimitConfig,
    bucket: TokenBucket,
) -> Response:
    """Create a 429 Too Many Requests response."""
    wait_time = bucket.get_wait_time()
    retry_after = max(1, int(wait_time) + 1)
    
    # Calculate reset time (when bucket will be full again)
    tokens_needed = config.burst_size - bucket.tokens
    reset_time = int(time.time() + (tokens_needed / config.refill_rate))
    
    headers = RateLimitHeaders(
        limit=config.requests_per_minute,
        remaining=0,
        reset=reset_time,
        retry_after=retry_after,
    )
    
    response = jsonify({
        "error": "rate_limit_exceeded",
        "message": "Too many requests. Please slow down.",
        "retry_after": retry_after,
        "limit": config.requests_per_minute,
        "retry_after_seconds": retry_after,
    })
    response.status_code = 429
    
    for key, value in headers.to_dict().items():
        response.headers[key] = value
    
    return response


def add_rate_limit_headers(
    response: Response,
    config: RateLimitConfig,
    bucket: TokenBucket,
    allowed: bool,
) -> Response:
    """Add rate limit headers to response."""
    # Calculate reset time
    tokens_needed = config.burst_size - bucket.tokens
    reset_time = int(time.time() + (tokens_needed / config.refill_rate))
    
    headers = RateLimitHeaders(
        limit=config.requests_per_minute,
        remaining=int(bucket.tokens),
        reset=reset_time,
    )
    
    for key, value in headers.to_dict().items():
        response.headers[key] = value
    
    return response


def rate_limit_middleware(
    config: Optional[RateLimitConfig] = None,
    get_config_for_client: Optional[Callable[[str], RateLimitConfig]] = None,
):
    """
    Rate limiting middleware decorator/factory.
    
    Usage:
        # Global default config
        @app.before_request
        def apply_rate_limit():
            return rate_limit_middleware()(request)
        
        # Custom config per endpoint
        @app.route("/api/v1/expensive")
        @rate_limit_middleware(config=RateLimitConfig(requests_per_minute=10))
        def expensive_endpoint():
            ...
        
        # Dynamic config per client
        @app.before_request
        def apply_rate_limit():
            return rate_limit_middleware(
                get_config_for_client=lambda client_id: load_config(client_id)
            )(request)
    """
    
    def middleware(request_obj=None):
        """Actual middleware logic."""
        # Get client identifier
        client_id = extract_client_id()
        
        # Get config for this client
        if get_config_for_client:
            config = get_config_for_client(client_id)
        elif config:
            config = config
        else:
            config = DEFAULT_RATE_LIMIT_CONFIG
        
        # Skip if disabled
        if not config.enabled:
            return None
        
        # Get or create bucket
        store = get_rate_limit_store()
        bucket = store.get_bucket(client_id, config)
        
        # Try to consume a token
        allowed, remaining = bucket.consume(1)
        
        # Store bucket state in Flask's g for later access
        g.rate_limit_client_id = client_id
        g.rate_limit_config = config
        g.rate_limit_bucket = bucket
        g.rate_limit_allowed = allowed
        
        if not allowed:
            logger.warning(
                f"Rate limit exceeded for client {client_id}: "
                f"{config.requests_per_minute} req/min, burst {config.burst_size}"
            )
            return rate_limit_exceeded_response(config, bucket)
        
        # Allow request to proceed (headers added in after_request)
        return None
    
    return middleware


def init_rate_limiting(app):
    """
    Initialize rate limiting for a Flask app.
    
    Sets up before_request and after_request handlers.
    """
    
    @app.before_request
    def check_rate_limit():
        """Check rate limit before processing request."""
        client_id = extract_client_id()
        
        # Get config (can be overridden per-route)
        config = getattr(request.endpoint, "rate_limit_config", None)
        if not config:
            config = DEFAULT_RATE_LIMIT_CONFIG
        
        # Skip if disabled
        if not config.enabled:
            return None
        
        # Get bucket
        store = get_rate_limit_store()
        bucket = store.get_bucket(client_id, config)
        
        # Store for later
        g.rate_limit_client_id = client_id
        g.rate_limit_config = config
        g.rate_limit_bucket = bucket
        
        # Consume token
        allowed, _ = bucket.consume(1)
        g.rate_limit_allowed = allowed
        
        if not allowed:
            logger.debug(f"Rate limit exceeded for {client_id}")
            return rate_limit_exceeded_response(config, bucket)
        
        return None
    
    @app.after_request
    def add_rate_limit_headers_to_response(response: Response) -> Response:
        """Add rate limit headers to all responses."""
        if hasattr(g, "rate_limit_config") and hasattr(g, "rate_limit_bucket"):
            response = add_rate_limit_headers(
                response,
                g.rate_limit_config,
                g.rate_limit_bucket,
                g.rate_limit_allowed,
            )
        return response
    
    logger.info("Rate limiting middleware initialized")


def with_rate_limit(config: RateLimitConfig):
    """
    Decorator to apply rate limiting to a specific endpoint.
    
    Usage:
        @app.route("/api/v1/expensive")
        @with_rate_limit(RateLimitConfig(requests_per_minute=10, burst_size=5))
        def expensive_endpoint():
            ...
    """
    def decorator(f):
        f.rate_limit_config = config
        return wraps(f)(f)
    return decorator
