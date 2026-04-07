"""Rate Limiter Advanced Engine — Slice 58.

Advanced rate limiting for PilotSuite Core.

Features:
- Multiple algorithms (token bucket, sliding window, fixed window, leaky bucket)
- Per-key limiting
- Hierarchical limits
- Burst allowance
- Rate limit headers
- Distributed rate limiting support
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import uuid

logger = logging.getLogger(__name__)


class Algorithm(Enum):
    """Rate limiting algorithms."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    LEAKY_BUCKET = "leaky_bucket"


class LimitScope(Enum):
    """Limit scope."""
    GLOBAL = "global"
    USER = "user"
    IP = "ip"
    API_KEY = "api_key"
    ENDPOINT = "endpoint"


@dataclass
class RateLimitResult:
    """Rate limit check result."""
    allowed: bool
    limit: int
    remaining: int
    reset_at: str
    retry_after: Optional[int] = None
    key: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "limit": self.limit,
            "remaining": self.remaining,
            "reset_at": self.reset_at,
            "retry_after": self.retry_after,
            "key": self.key,
        }


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    config_id: str
    name: str
    algorithm: Algorithm
    limit: int
    window_seconds: int
    burst_limit: Optional[int] = None
    scope: LimitScope = LimitScope.GLOBAL
    enabled: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "config_id": self.config_id,
            "name": self.name,
            "algorithm": self.algorithm.value,
            "limit": self.limit,
            "window_seconds": self.window_seconds,
            "burst_limit": self.burst_limit,
            "scope": self.scope.value,
            "enabled": self.enabled,
            "created_at": self.created_at,
        }


class TokenBucket:
    """Token bucket rate limiter."""
    
    def __init__(self, capacity: int, refill_rate: float):
        self.capacity = capacity
        self.refill_rate = refill_rate  # tokens per second
        self.tokens = capacity
        self.last_refill = time.time()
        self._lock = threading.Lock()
    
    def acquire(self, tokens: int = 1) -> Tuple[bool, float]:
        """Try to acquire tokens. Returns (success, wait_time)."""
        with self._lock:
            now = time.time()
            
            # Refill tokens
            elapsed = now - self.last_refill
            self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
            self.last_refill = now
            
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True, 0.0
            else:
                # Calculate wait time
                wait_time = (tokens - self.tokens) / self.refill_rate
                return False, wait_time
    
    def get_remaining(self) -> int:
        """Get remaining tokens."""
        with self._lock:
            return int(self.tokens)


class SlidingWindowLog:
    """Sliding window log rate limiter."""
    
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self.requests: List[float] = []
        self._lock = threading.Lock()
    
    def acquire(self) -> Tuple[bool, int]:
        """Try to acquire. Returns (success, remaining)."""
        with self._lock:
            now = time.time()
            window_start = now - self.window_seconds
            
            # Remove old requests
            self.requests = [t for t in self.requests if t > window_start]
            
            if len(self.requests) < self.limit:
                self.requests.append(now)
                return True, self.limit - len(self.requests)
            else:
                # Calculate remaining time until oldest request expires
                if self.requests:
                    oldest = self.requests[0]
                    retry_after = int(oldest + self.window_seconds - now) + 1
                else:
                    retry_after = self.window_seconds
                
                return False, 0
    
    def get_remaining(self) -> int:
        """Get remaining requests."""
        with self._lock:
            now = time.time()
            window_start = now - self.window_seconds
            self.requests = [t for t in self.requests if t > window_start]
            return self.limit - len(self.requests)


class FixedWindow:
    """Fixed window rate limiter."""
    
    def __init__(self, limit: int, window_seconds: int):
        self.limit = limit
        self.window_seconds = window_seconds
        self.count = 0
        self.window_start = time.time()
        self._lock = threading.Lock()
    
    def acquire(self) -> Tuple[bool, int, float]:
        """Try to acquire. Returns (success, remaining, reset_time)."""
        with self._lock:
            now = time.time()
            
            # Check if window has expired
            if now - self.window_start >= self.window_seconds:
                self.window_start = now
                self.count = 0
            
            if self.count < self.limit:
                self.count += 1
                reset_time = self.window_start + self.window_seconds
                return True, self.limit - self.count, reset_time
            else:
                reset_time = self.window_start + self.window_seconds
                return False, 0, reset_time
    
    def get_remaining(self) -> int:
        """Get remaining requests."""
        with self._lock:
            now = time.time()
            if now - self.window_start >= self.window_seconds:
                return self.limit
            return self.limit - self.count


class LeakyBucket:
    """Leaky bucket rate limiter."""
    
    def __init__(self, capacity: int, leak_rate: float):
        self.capacity = capacity
        self.leak_rate = leak_rate  # requests per second
        self.water = 0.0
        self.last_leak = time.time()
        self._lock = threading.Lock()
    
    def acquire(self) -> Tuple[bool, float]:
        """Try to acquire. Returns (success, wait_time)."""
        with self._lock:
            now = time.time()
            
            # Leak water
            elapsed = now - self.last_leak
            self.water = max(0, self.water - elapsed * self.leak_rate)
            self.last_leak = now
            
            projected = self.water + 1
            if projected <= self.capacity:
                self.water = projected
                return True, 0.0
            else:
                # Calculate wait time for enough water to leak out to admit one more request
                wait_time = (projected - self.capacity) / self.leak_rate
                return False, wait_time
    
    def get_remaining(self) -> int:
        """Get remaining capacity."""
        with self._lock:
            return int(self.capacity - self.water)


class RateLimiterEngine:
    """Advanced rate limiter engine."""
    
    def __init__(self):
        self._configs: Dict[str, RateLimitConfig] = {}
        self._limiters: Dict[str, Dict[str, Any]] = {}  # config_id -> {key -> limiter}
        self._lock = threading.Lock()
        
        # Statistics
        self._stats = {
            "total_requests": 0,
            "allowed_requests": 0,
            "denied_requests": 0,
            "by_config": {},
            "by_key": {},
        }
    
    def create_config(self, name: str, algorithm: Algorithm,
                     limit: int, window_seconds: int,
                     burst_limit: Optional[int] = None,
                     scope: LimitScope = LimitScope.GLOBAL) -> str:
        """Create rate limit configuration."""
        config_id = f"rlc_{uuid.uuid4().hex[:16]}"
        
        config = RateLimitConfig(
            config_id=config_id,
            name=name,
            algorithm=algorithm,
            limit=limit,
            window_seconds=window_seconds,
            burst_limit=burst_limit,
            scope=scope,
        )
        
        with self._lock:
            self._configs[config_id] = config
            self._limiters[config_id] = {}
        
        logger.info("Rate limit config created: %s (%s)", name, config_id)
        
        return config_id
    
    def update_config(self, config_id: str,
                     limit: Optional[int] = None,
                     window_seconds: Optional[int] = None,
                     burst_limit: Optional[int] = None,
                     enabled: Optional[bool] = None) -> bool:
        """Update rate limit configuration."""
        with self._lock:
            config = self._configs.get(config_id)
            
            if not config:
                return False
            
            if limit is not None:
                config.limit = limit
            if window_seconds is not None:
                config.window_seconds = window_seconds
            if burst_limit is not None:
                config.burst_limit = burst_limit
            if enabled is not None:
                config.enabled = enabled
        
        return True
    
    def delete_config(self, config_id: str) -> bool:
        """Delete rate limit configuration."""
        with self._lock:
            if config_id not in self._configs:
                return False
            
            del self._configs[config_id]
            del self._limiters[config_id]
        
        return True
    
    def get_config(self, config_id: str) -> Optional[RateLimitConfig]:
        """Get configuration by ID."""
        return self._configs.get(config_id)
    
    def list_configs(self) -> List[RateLimitConfig]:
        """List all configurations."""
        return list(self._configs.values())
    
    def check(self, config_id: str, key: str = "default") -> RateLimitResult:
        """Check rate limit for key."""
        config = self._configs.get(config_id)
        
        if not config or not config.enabled:
            return RateLimitResult(
                allowed=True,
                limit=0,
                remaining=0,
                reset_at=datetime.now(timezone.utc).isoformat(),
                key=key,
            )
        
        with self._lock:
            # Get or create limiter for key
            if key not in self._limiters[config_id]:
                self._limiters[config_id][key] = self._create_limiter(config)
            
            limiter = self._limiters[config_id][key]
        
        # Check limit
        allowed, extra = self._acquire(limiter, config)
        
        # Calculate reset time
        reset_at = self._calculate_reset(config)
        
        # Update statistics
        self._stats["total_requests"] += 1
        self._stats["by_config"][config_id] = self._stats["by_config"].get(config_id, 0) + 1
        self._stats["by_key"][key] = self._stats["by_key"].get(key, 0) + 1
        
        if allowed:
            self._stats["allowed_requests"] += 1
        else:
            self._stats["denied_requests"] += 1
        
        retry_after = None if allowed else extra
        
        return RateLimitResult(
            allowed=allowed,
            limit=config.limit,
            remaining=limiter.get_remaining(),
            reset_at=reset_at,
            retry_after=int(retry_after) if retry_after else None,
            key=key,
        )
    
    def _create_limiter(self, config: RateLimitConfig) -> Any:
        """Create limiter based on algorithm."""
        if config.algorithm == Algorithm.TOKEN_BUCKET:
            burst = config.burst_limit or config.limit
            refill_rate = config.limit / config.window_seconds
            return TokenBucket(burst, refill_rate)
        
        elif config.algorithm == Algorithm.SLIDING_WINDOW:
            return SlidingWindowLog(config.limit, config.window_seconds)
        
        elif config.algorithm == Algorithm.FIXED_WINDOW:
            return FixedWindow(config.limit, config.window_seconds)
        
        elif config.algorithm == Algorithm.LEAKY_BUCKET:
            leak_rate = config.limit / config.window_seconds
            capacity = config.burst_limit or config.limit
            return LeakyBucket(capacity, leak_rate)
        
        else:
            raise ValueError(f"Unknown algorithm: {config.algorithm}")
    
    def _acquire(self, limiter: Any, config: RateLimitConfig) -> Tuple[bool, float]:
        """Acquire from limiter."""
        if config.algorithm == Algorithm.TOKEN_BUCKET:
            allowed, wait = limiter.acquire()
            return allowed, wait
        
        elif config.algorithm == Algorithm.SLIDING_WINDOW:
            allowed, remaining = limiter.acquire()
            return allowed, config.window_seconds
        
        elif config.algorithm == Algorithm.FIXED_WINDOW:
            allowed, remaining, reset = limiter.acquire()
            return allowed, max(0, reset - time.time())
        
        elif config.algorithm == Algorithm.LEAKY_BUCKET:
            allowed, wait = limiter.acquire()
            return allowed, wait
        
        return True, 0.0
    
    def _calculate_reset(self, config: RateLimitConfig) -> str:
        """Calculate reset time."""
        now = datetime.now(timezone.utc)
        reset = now + timedelta(seconds=config.window_seconds)
        return reset.isoformat()
    
    def reset_key(self, config_id: str, key: str) -> bool:
        """Reset rate limit for specific key."""
        with self._lock:
            if config_id not in self._limiters:
                return False
            
            if key in self._limiters[config_id]:
                del self._limiters[config_id][key]
                return True
            
            return False
    
    def reset_all(self, config_id: str) -> int:
        """Reset all keys for config."""
        with self._lock:
            if config_id not in self._limiters:
                return 0
            
            count = len(self._limiters[config_id])
            self._limiters[config_id].clear()
            return count
    
    def get_key_status(self, config_id: str, key: str) -> Optional[Dict[str, Any]]:
        """Get status for specific key."""
        with self._lock:
            if config_id not in self._limiters:
                return None
            
            if key not in self._limiters[config_id]:
                return None
            
            limiter = self._limiters[config_id][key]
            config = self._configs[config_id]
            
            return {
                "key": key,
                "config_id": config_id,
                "algorithm": config.algorithm.value,
                "limit": config.limit,
                "remaining": limiter.get_remaining(),
                "window_seconds": config.window_seconds,
            }
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get rate limiter statistics."""
        with self._lock:
            total_keys = sum(len(keys) for keys in self._limiters.values())
            
            return {
                **self._stats,
                "total_configs": len(self._configs),
                "total_keys": total_keys,
            }
    
    def clear(self) -> int:
        """Clear all configurations and limiters."""
        with self._lock:
            count = len(self._configs)
            self._configs.clear()
            self._limiters.clear()
            return count


def create_rate_limiter_engine() -> RateLimiterEngine:
    """Factory function to create rate limiter engine."""
    return RateLimiterEngine()
