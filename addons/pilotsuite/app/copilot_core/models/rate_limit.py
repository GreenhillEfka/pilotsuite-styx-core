"""
Rate Limiting Models

Dataclasses and enums for API rate limiting configuration and state.

Features:
- Token Bucket Algorithm configuration
- Per-API-Key limits
- Default: 100 requests/min, burst: 20
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum
import time


class RateLimitAlgorithm(str, Enum):
    """Rate limiting algorithm types."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"


@dataclass
class RateLimitConfig:
    """
    Rate limit configuration for a client/API key.
    
    Token Bucket Algorithm:
    - Tokens refill at a constant rate (requests_per_minute / 60 per second)
    - Bucket can hold up to burst_size tokens
    - Each request consumes 1 token
    - When bucket is empty, requests are rejected with 429
    """
    requests_per_minute: int = 100
    burst_size: int = 20
    algorithm: RateLimitAlgorithm = RateLimitAlgorithm.TOKEN_BUCKET
    enabled: bool = True
    
    # Optional per-key override
    api_key: Optional[str] = None
    
    @property
    def refill_rate(self) -> float:
        """Tokens added per second."""
        return self.requests_per_minute / 60.0
    
    @property
    def refill_interval(self) -> float:
        """Seconds between token refills (for discrete implementations)."""
        return 60.0 / self.requests_per_minute
    
    def to_dict(self) -> dict:
        """Serialize to JSON-safe dict."""
        return {
            "requests_per_minute": self.requests_per_minute,
            "burst_size": self.burst_size,
            "algorithm": self.algorithm.value,
            "enabled": self.enabled,
            "api_key": self.api_key,
            "refill_rate": self.refill_rate,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> RateLimitConfig:
        """Deserialize from dict."""
        algorithm = data.get("algorithm", "token_bucket")
        if isinstance(algorithm, str):
            algorithm = RateLimitAlgorithm(algorithm)
        
        return cls(
            requests_per_minute=data.get("requests_per_minute", 100),
            burst_size=data.get("burst_size", 20),
            algorithm=algorithm,
            enabled=data.get("enabled", True),
            api_key=data.get("api_key"),
        )


@dataclass
class TokenBucket:
    """
    Token bucket state for a single client/API key.
    
    Thread-safe token bucket implementation for rate limiting.
    """
    capacity: int  # Maximum tokens (burst_size)
    tokens: float  # Current tokens (can be float for smooth refill)
    refill_rate: float  # Tokens per second
    last_refill: float  # Unix timestamp of last refill
    
    def __post_init__(self):
        if self.last_refill == 0:
            self.last_refill = time.time()
    
    def consume(self, tokens: int = 1) -> tuple[bool, float]:
        """
        Try to consume tokens from the bucket.
        
        Returns:
            Tuple of (success, remaining_tokens)
        """
        now = time.time()
        
        # Refill tokens based on elapsed time
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now
        
        if self.tokens >= tokens:
            self.tokens -= tokens
            return True, self.tokens
        else:
            return False, self.tokens
    
    def get_wait_time(self, tokens: int = 1) -> float:
        """Calculate seconds to wait until tokens are available."""
        if self.tokens >= tokens:
            return 0.0
        needed = tokens - self.tokens
        return needed / self.refill_rate
    
    def to_dict(self) -> dict:
        """Serialize bucket state."""
        return {
            "capacity": self.capacity,
            "tokens": round(self.tokens, 2),
            "refill_rate": self.refill_rate,
            "last_refill": self.last_refill,
        }
    
    @classmethod
    def from_config(cls, config: RateLimitConfig) -> TokenBucket:
        """Create a new bucket from config."""
        return cls(
            capacity=config.burst_size,
            tokens=float(config.burst_size),  # Start full
            refill_rate=config.refill_rate,
            last_refill=time.time(),
        )


@dataclass
class RateLimitHeaders:
    """
    Rate limit response headers.
    
    Standard headers for communicating rate limit status to clients.
    """
    limit: int  # X-RateLimit-Limit: Maximum requests per window
    remaining: int  # X-RateLimit-Remaining: Requests remaining
    reset: int  # X-RateLimit-Reset: Unix timestamp when limit resets
    retry_after: Optional[int] = None  # Retry-After: Seconds to wait (only on 429)
    
    def to_dict(self) -> dict:
        """Convert to header dict."""
        headers = {
            "X-RateLimit-Limit": str(self.limit),
            "X-RateLimit-Remaining": str(max(0, self.remaining)),
            "X-RateLimit-Reset": str(self.reset),
        }
        if self.retry_after is not None:
            headers["Retry-After"] = str(self.retry_after)
        return headers


@dataclass
class RateLimitStatus:
    """
    Rate limit status for monitoring/debugging.
    """
    client_id: str
    config: RateLimitConfig
    bucket: TokenBucket
    is_limited: bool
    requests_made: int = 0
    requests_rejected: int = 0
    last_request: Optional[float] = None
    
    def to_dict(self) -> dict:
        """Serialize status."""
        return {
            "client_id": self.client_id,
            "config": self.config.to_dict(),
            "bucket": self.bucket.to_dict(),
            "is_limited": self.is_limited,
            "requests_made": self.requests_made,
            "requests_rejected": self.requests_rejected,
            "last_request": self.last_request,
        }


# Default configuration
DEFAULT_RATE_LIMIT_CONFIG = RateLimitConfig(
    requests_per_minute=100,
    burst_size=20,
    algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
    enabled=True,
)
