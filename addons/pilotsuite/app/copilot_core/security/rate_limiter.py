"""Token Bucket Rate Limiter for API endpoints.

Implements a token bucket algorithm for rate limiting with support for:
- Per-client rate limiting (by API key or IP)
- Configurable requests per minute
- Automatic token refill
- Thread-safe operations
"""

from __future__ import annotations

import time
import os
import logging
from threading import Lock
from typing import Any, Dict, Optional, Tuple
from functools import wraps
from collections import defaultdict

from flask import jsonify, request, g

logger = logging.getLogger(__name__)


class TokenBucket:
    """Token bucket implementation for rate limiting.
    
    Each bucket holds tokens that are consumed on requests and refilled over time.
    """
    
    def __init__(self, capacity: int, refill_rate: float):
        """Initialize token bucket.
        
        Args:
            capacity: Maximum number of tokens (burst capacity)
            refill_rate: Tokens added per second
        """
        self.capacity = capacity
        self.refill_rate = refill_rate
        self.tokens = float(capacity)
        self.last_refill = time.time()
        self._lock = Lock()
    
    def _refill(self) -> None:
        """Refill tokens based on elapsed time."""
        now = time.time()
        elapsed = now - self.last_refill
        tokens_to_add = elapsed * self.refill_rate
        self.tokens = min(self.capacity, self.tokens + tokens_to_add)
        self.last_refill = now
    
    def consume(self, tokens: int = 1) -> bool:
        """Try to consume tokens.
        
        Args:
            tokens: Number of tokens to consume
            
        Returns:
            True if tokens were consumed, False if insufficient tokens
        """
        with self._lock:
            self._refill()
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            return False
    
    def get_tokens(self) -> float:
        """Get current token count (after refill)."""
        with self._lock:
            self._refill()
            return self.tokens
    
    def reset(self) -> None:
        """Reset bucket to full capacity."""
        with self._lock:
            self.tokens = float(self.capacity)
            self.last_refill = time.time()


class RateLimiter:
    """Rate limiter using token bucket algorithm.
    
    Features:
    - 100 requests/minute per client (default)
    - Per-client tracking by API key or IP
    - Configurable limits per endpoint
    - Thread-safe operations
    """
    
    def __init__(
        self,
        default_capacity: int = 100,
        default_refill_rate: float = 100.0 / 60.0,  # 100 requests per minute
        cleanup_interval: int = 300,  # Clean up old buckets every 5 minutes
    ):
        """Initialize rate limiter.
        
        Args:
            default_capacity: Default bucket capacity (requests per minute)
            default_refill_rate: Default refill rate (tokens per second)
            cleanup_interval: Seconds between cleanup of inactive buckets
        """
        self.default_capacity = default_capacity
        self.default_refill_rate = default_refill_rate
        self.cleanup_interval = cleanup_interval
        
        # Per-client buckets: key -> TokenBucket
        self._buckets: Dict[str, TokenBucket] = {}
        self._bucket_lock = Lock()
        
        # Per-endpoint overrides: endpoint -> (capacity, refill_rate)
        self._endpoint_limits: Dict[str, Tuple[int, float]] = {}
        
        # Last cleanup time
        self._last_cleanup = time.time()
        
        # Load limits from environment
        self._load_env_limits()
    
    def _load_env_limits(self) -> None:
        """Load endpoint-specific limits from environment variables."""
        # Format: COPILOT_RATE_LIMIT_<ENDPOINT>=<requests_per_min>
        # Example: COPILOT_RATE_LIMIT_EVENTS=200
        for key, value in os.environ.items():
            if key.startswith("COPILOT_RATE_LIMIT_"):
                endpoint = "/" + key.replace("COPILOT_RATE_LIMIT_", "").lower().replace("_", "/")
                try:
                    requests_per_min = int(value)
                    capacity = requests_per_min
                    refill_rate = requests_per_min / 60.0
                    self._endpoint_limits[endpoint] = (capacity, refill_rate)
                    logger.debug(f"Rate limit for {endpoint}: {requests_per_min} req/min")
                except ValueError:
                    logger.warning(f"Invalid rate limit value for {key}: {value}")
    
    def set_endpoint_limit(
        self,
        endpoint: str,
        requests_per_minute: int,
    ) -> None:
        """Set rate limit for a specific endpoint.
        
        Args:
            endpoint: API endpoint path
            requests_per_minute: Maximum requests per minute
        """
        capacity = requests_per_minute
        refill_rate = requests_per_minute / 60.0
        self._endpoint_limits[endpoint] = (capacity, refill_rate)
        logger.info(f"Set rate limit for {endpoint}: {requests_per_minute} req/min")
    
    def _get_bucket_params(self, endpoint: str) -> Tuple[int, float]:
        """Get bucket parameters for an endpoint."""
        if endpoint in self._endpoint_limits:
            return self._endpoint_limits[endpoint]
        return (self.default_capacity, self.default_refill_rate)
    
    def _get_or_create_bucket(self, key: str, endpoint: str) -> TokenBucket:
        """Get or create a token bucket for a client/endpoint combination."""
        with self._bucket_lock:
            # Cleanup old buckets periodically
            now = time.time()
            if now - self._last_cleanup > self.cleanup_interval:
                self._cleanup_inactive_buckets()
                self._last_cleanup = now
            
            # Create bucket key (client + endpoint for per-endpoint limiting)
            bucket_key = f"{key}:{endpoint}"
            
            if bucket_key not in self._buckets:
                capacity, refill_rate = self._get_bucket_params(endpoint)
                self._buckets[bucket_key] = TokenBucket(capacity, refill_rate)
                logger.debug(f"Created new bucket for {bucket_key} (capacity={capacity})")
            
            return self._buckets[bucket_key]
    
    def _cleanup_inactive_buckets(self) -> None:
        """Remove buckets that haven't been used recently."""
        # Keep buckets active for 10 minutes after last use
        # This is a simplified cleanup - in production, track last access time
        inactive_threshold = 600  # 10 minutes
        
        # For now, just limit total bucket count
        max_buckets = 10000
        if len(self._buckets) > max_buckets:
            # Remove oldest buckets (simplified)
            keys_to_remove = list(self._buckets.keys())[:max_buckets // 2]
            for key in keys_to_remove:
                del self._buckets[key]
            logger.info(f"Cleaned up {len(keys_to_remove)} inactive buckets")
    
    def is_allowed(self, client_key: str, endpoint: str) -> Tuple[bool, Dict[str, Any]]:
        """Check if a request is allowed.
        
        Args:
            client_key: Client identifier (API key, IP, etc.)
            endpoint: API endpoint path
            
        Returns:
            Tuple of (allowed: bool, info: dict with rate limit details)
        """
        bucket = self._get_or_create_bucket(client_key, endpoint)
        
        allowed = bucket.consume(1)
        tokens_remaining = bucket.get_tokens()
        
        # Calculate reset time (time until bucket is full)
        capacity, refill_rate = self._get_bucket_params(endpoint)
        tokens_needed = capacity - tokens_remaining
        reset_seconds = tokens_needed / refill_rate if refill_rate > 0 else 0
        
        info = {
            "remaining": int(tokens_remaining),
            "limit": capacity,
            "reset": int(time.time() + reset_seconds),
            "refill_rate": refill_rate,
        }
        
        if not allowed:
            logger.warning(
                f"Rate limit exceeded for {client_key} on {endpoint} "
                f"(remaining={info['remaining']}, limit={info['limit']})"
            )
        
        return allowed, info
    
    def get_client_key(self) -> str:
        """Extract client key from current request.
        
        Priority:
        1. X-API-Key header
        2. X-Auth-Token header
        3. Bearer token from Authorization header
        4. Client IP address
        """
        try:
            # Check API key header
            api_key = request.headers.get("X-API-Key", "").strip()
            if api_key:
                return f"apikey:{api_key[:16]}"
            
            # Check auth token
            auth_token = request.headers.get("X-Auth-Token", "").strip()
            if auth_token:
                return f"token:{auth_token[:16]}"
            
            # Check Bearer token
            auth_header = request.headers.get("Authorization", "").strip()
            if auth_header.startswith("Bearer "):
                token = auth_header[7:].strip()
                if token:
                    return f"bearer:{token[:16]}"
            
            # Fall back to IP
            client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "unknown")
            return f"ip:{client_ip}"
        except RuntimeError:
            # Outside request context
            return "unknown"
    
    def reset(self, client_key: Optional[str] = None) -> None:
        """Reset rate limit for a client or all clients.
        
        Args:
            client_key: Client identifier or None to reset all
        """
        with self._bucket_lock:
            if client_key:
                # Reset all buckets for this client
                keys_to_reset = [k for k in self._buckets.keys() if k.startswith(f"{client_key}:")]
                for key in keys_to_reset:
                    self._buckets[key].reset()
                logger.info(f"Reset rate limit for client {client_key}")
            else:
                self._buckets.clear()
                logger.info("Reset all rate limits")


# Global rate limiter instance
_rate_limiter: Optional[RateLimiter] = None


def get_rate_limiter() -> RateLimiter:
    """Get the global rate limiter instance."""
    global _rate_limiter
    if _rate_limiter is None:
        # Default: 100 requests per minute
        _rate_limiter = RateLimiter(
            default_capacity=100,
            default_refill_rate=100.0 / 60.0,
        )
    return _rate_limiter


def rate_limit(endpoint: Optional[str] = None):
    """Decorator to apply rate limiting to an endpoint.
    
    Args:
        endpoint: Override endpoint path (default: use request.path)
        
    Returns:
        Decorator function
        
    Example:
        @bp.get("/users")
        @rate_limit("/api/v1/users")
        def get_users():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            limiter = get_rate_limiter()
            
            # Determine endpoint
            ep = endpoint or request.path
            
            # Get client key
            client_key = limiter.get_client_key()
            
            # Check rate limit
            allowed, info = limiter.is_allowed(client_key, ep)
            
            # Store rate limit info in Flask g object for response headers
            g.rate_limit_info = info
            
            if not allowed:
                # Log security event
                from .security_logs import get_security_logger
                sec_logger = get_security_logger()
                sec_logger.log_rate_limit_exceeded(client_key, ep)
                
                response = jsonify({
                    "ok": False,
                    "error": "rate_limit_exceeded",
                    "message": "Too many requests. Please try again later.",
                    "rate_limit": info,
                })
                response.status_code = 429
                _add_rate_limit_headers(response, info)
                return response
            
            # Call the actual function
            result = f(*args, **kwargs)
            
            # Add rate limit headers to response
            try:
                from flask import make_response
                if not isinstance(result, tuple):
                    response = make_response(result)
                else:
                    response = make_response(result[0], result[1] if len(result) > 1 else 200)
                _add_rate_limit_headers(response, info)
                return response
            except RuntimeError:
                # Outside request context
                return result
        
        return decorated_function
    return decorator


def _add_rate_limit_headers(response, info: Dict[str, Any]) -> None:
    """Add rate limit headers to response."""
    response.headers["X-RateLimit-Limit"] = str(info["limit"])
    response.headers["X-RateLimit-Remaining"] = str(info["remaining"])
    response.headers["X-RateLimit-Reset"] = str(info["reset"])


def get_rate_limit_status() -> Dict[str, Any]:
    """Get rate limiter status for monitoring."""
    limiter = get_rate_limiter()
    return {
        "default_capacity": limiter.default_capacity,
        "default_refill_rate": limiter.default_refill_rate,
        "active_buckets": len(limiter._buckets),
        "endpoint_overrides": {
            ep: {"capacity": cap, "refill_rate": rate}
            for ep, (cap, rate) in limiter._endpoint_limits.items()
        },
    }
