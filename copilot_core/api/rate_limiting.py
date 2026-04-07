"""P1-005: API Rate Limiting — Token Bucket, Per-User/IP Limits, Graceful Degradation."""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Dict, Optional, Tuple
from enum import Enum

logger = logging.getLogger(__name__)


class RateLimitAction(Enum):
    """Action when rate limit exceeded."""
    REJECT = "reject"  # Return 429
    QUEUE = "queue"  # Queue for later
    DEGRADE = "degrade"  # Return cached/stale data


@dataclass
class RateLimitConfig:
    """Configuration for rate limiting."""
    requests_per_second: float = 10.0
    burst_size: int = 20
    per_user_limit: int = 100
    per_ip_limit: int = 50
    action_on_exceed: RateLimitAction = RateLimitAction.REJECT
    retry_after_seconds: float = 1.0


@dataclass
class TokenBucket:
    """Token bucket for rate limiting."""
    capacity: float
    tokens: float
    refill_rate: float  # tokens per second
    last_refill: float = field(default_factory=time.time)

    def consume(self, tokens: float = 1.0) -> bool:
        """Try to consume tokens. Returns True if successful."""
        now = time.time()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

        if self.tokens >= tokens:
            self.tokens -= tokens
            return True
        return False

    def get_wait_time(self, tokens: float = 1.0) -> float:
        """Get time to wait until tokens available."""
        if self.tokens >= tokens:
            return 0.0
        needed = tokens - self.tokens
        return needed / self.refill_rate


@dataclass
class RateLimitStats:
    """Statistics for rate limiting."""
    total_requests: int = 0
    allowed_requests: int = 0
    rejected_requests: int = 0
    queued_requests: int = 0
    degraded_requests: int = 0


class RateLimiter:
    """Central rate limiter with token bucket algorithm."""

    def __init__(self, config: Optional[RateLimitConfig] = None):
        self.config = config or RateLimitConfig()
        self._global_bucket = TokenBucket(
            capacity=self.config.burst_size,
            tokens=self.config.burst_size,
            refill_rate=self.config.requests_per_second
        )
        self._user_buckets: Dict[str, TokenBucket] = {}
        self._ip_buckets: Dict[str, TokenBucket] = {}
        self._stats = RateLimitStats()
        self._request_queue: list = []
        self._whitelist: set = set()
        self._blacklist: set = set()

    def add_to_whitelist(self, identifier: str):
        """Add identifier to whitelist (no rate limiting)."""
        self._whitelist.add(identifier)
        logger.info(f"Added to whitelist: {identifier}")

    def add_to_blacklist(self, identifier: str):
        """Add identifier to blacklist (always rejected)."""
        self._blacklist.add(identifier)
        logger.warning(f"Added to blacklist: {identifier}")

    def _get_user_bucket(self, user_id: str) -> TokenBucket:
        """Get or create user-specific bucket."""
        if user_id not in self._user_buckets:
            self._user_buckets[user_id] = TokenBucket(
                capacity=self.config.per_user_limit,
                tokens=self.config.per_user_limit,
                refill_rate=self.config.per_user_limit / 60.0  # per minute
            )
        return self._user_buckets[user_id]

    def _get_ip_bucket(self, ip: str) -> TokenBucket:
        """Get or create IP-specific bucket."""
        if ip not in self._ip_buckets:
            self._ip_buckets[ip] = TokenBucket(
                capacity=self.config.per_ip_limit,
                tokens=self.config.per_ip_limit,
                refill_rate=self.config.per_ip_limit / 60.0
            )
        return self._ip_buckets[ip]

    def check_rate_limit(
        self,
        user_id: Optional[str] = None,
        ip: Optional[str] = None,
        tokens: float = 1.0
    ) -> Tuple[bool, Optional[float], RateLimitAction]:
        """
        Check if request is allowed.
        Returns: (allowed, retry_after_seconds, action)
        """
        self._stats.total_requests += 1

        # Check blacklist
        identifier = user_id or ip
        if identifier and identifier in self._blacklist:
            self._stats.rejected_requests += 1
            return False, None, RateLimitAction.REJECT

        # Check whitelist
        if identifier and identifier in self._whitelist:
            self._stats.allowed_requests += 1
            return True, None, RateLimitAction.REJECT

        # Check global bucket
        if not self._global_bucket.consume(tokens):
            wait_time = self._global_bucket.get_wait_time(tokens)
            self._stats.rejected_requests += 1
            return False, wait_time, self.config.action_on_exceed

        # Check user bucket
        if user_id:
            user_bucket = self._get_user_bucket(user_id)
            if not user_bucket.consume(tokens):
                wait_time = user_bucket.get_wait_time(tokens)
                self._stats.rejected_requests += 1
                return False, wait_time, self.config.action_on_exceed

        # Check IP bucket
        if ip:
            ip_bucket = self._get_ip_bucket(ip)
            if not ip_bucket.consume(tokens):
                wait_time = ip_bucket.get_wait_time(tokens)
                self._stats.rejected_requests += 1
                return False, wait_time, self.config.action_on_exceed

        self._stats.allowed_requests += 1
        return True, None, RateLimitAction.REJECT

    def get_stats(self) -> Dict[str, any]:
        """Get rate limiter statistics."""
        return {
            "total_requests": self._stats.total_requests,
            "allowed_requests": self._stats.allowed_requests,
            "rejected_requests": self._stats.rejected_requests,
            "queued_requests": self._stats.queued_requests,
            "degraded_requests": self._stats.degraded_requests,
            "rejection_rate": self._stats.rejected_requests / max(1, self._stats.total_requests),
            "user_buckets": len(self._user_buckets),
            "ip_buckets": len(self._ip_buckets),
        }

    def get_rate_limit_headers(self) -> Dict[str, str]:
        """Get X-RateLimit-* headers for response."""
        return {
            "X-RateLimit-Limit": str(int(self.config.requests_per_second * 60)),
            "X-RateLimit-Remaining": str(int(self._global_bucket.tokens)),
            "X-RateLimit-Reset": str(int(time.time() + self._global_bucket.get_wait_time())),
        }


class GracefulDegradation:
    """Handles graceful degradation when rate limited."""

    def __init__(self, cache: Optional[any] = None):
        self.cache = cache
        self._fallbacks: Dict[str, callable] = {}

    def register_fallback(self, endpoint: str, fallback: callable):
        """Register fallback handler for endpoint."""
        self._fallbacks[endpoint] = fallback

    def get_cached_or_fallback(
        self,
        endpoint: str,
        request_params: Optional[Dict] = None
    ) -> Optional[any]:
        """Get cached data or fallback result."""
        # Try cache first
        if self.cache:
            cached = self.cache.get(endpoint, request_params)
            if cached:
                logger.info(f"Returning cached data for {endpoint}")
                return cached

        # Try fallback
        if endpoint in self._fallbacks:
            try:
                result = self._fallbacks[endpoint]()
                logger.info(f"Returning fallback data for {endpoint}")
                return result
            except Exception as e:
                logger.error(f"Fallback failed for {endpoint}: {e}")

        return None


# Global default rate limiter
default_rate_limiter: Optional[RateLimiter] = None


def init_rate_limiter(config: Optional[RateLimitConfig] = None) -> RateLimiter:
    """Initialize global rate limiter."""
    global default_rate_limiter
    default_rate_limiter = RateLimiter(config)
    return default_rate_limiter


def rate_limit_check(user_id: Optional[str] = None, ip: Optional[str] = None) -> Tuple[bool, Optional[float]]:
    """Convenience function for rate limit checking."""
    if default_rate_limiter:
        allowed, retry_after, _ = default_rate_limiter.check_rate_limit(user_id, ip)
        return allowed, retry_after
    return True, None
