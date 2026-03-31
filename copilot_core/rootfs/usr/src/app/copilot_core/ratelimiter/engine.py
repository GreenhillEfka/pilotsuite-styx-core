"""Rate Limiter Engine — Slice 39.

Rate limiting for PilotSuite Core APIs and operations.

Features:
- Multiple algorithms (token bucket, sliding window, fixed window)
- Per-key and global limits
- Burst allowance
- Rate limit headers
- Distributed rate limiting support
- Quota management
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional, Tuple
from enum import Enum
import uuid
import threading

logger = logging.getLogger(__name__)


class RateLimitAlgorithm(Enum):
    """Rate limiting algorithm."""
    TOKEN_BUCKET = "token_bucket"
    SLIDING_WINDOW = "sliding_window"
    FIXED_WINDOW = "fixed_window"
    LEAKY_BUCKET = "leaky_bucket"


@dataclass
class RateLimitConfig:
    """Rate limit configuration."""
    limit_id: str
    algorithm: RateLimitAlgorithm
    max_requests: int
    window_seconds: int
    burst_size: int = 0  # Additional burst allowance
    key_prefix: str = ""
    enabled: bool = True
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "limit_id": self.limit_id,
            "algorithm": self.algorithm.value,
            "max_requests": self.max_requests,
            "window_seconds": self.window_seconds,
            "burst_size": self.burst_size,
            "key_prefix": self.key_prefix,
            "enabled": self.enabled,
        }


@dataclass
class RateLimitResult:
    """Result of rate limit check."""
    allowed: bool
    remaining: int
    reset_at: str
    retry_after_seconds: int = 0
    limit: int = 0
    key: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "allowed": self.allowed,
            "remaining": self.remaining,
            "reset_at": self.reset_at,
            "retry_after_seconds": self.retry_after_seconds,
            "limit": self.limit,
            "key": self.key,
        }


@dataclass
class TokenBucket:
    """Token bucket state."""
    tokens: float
    last_update: str
    max_tokens: int
    refill_rate: float  # tokens per second


@dataclass
class WindowState:
    """Window-based rate limit state."""
    count: int
    window_start: str
    window_seconds: int


class RateLimiterEngine:
    """Rate limiting engine."""
    
    def __init__(self):
        self._configs: Dict[str, RateLimitConfig] = {}
        self._token_buckets: Dict[str, TokenBucket] = {}
        self._sliding_windows: Dict[str, List[str]] = {}  # key -> [timestamps]
        self._fixed_windows: Dict[str, WindowState] = {}
        self._leaky_buckets: Dict[str, Tuple[int, str]] = {}  # key -> (water_level, last_update)
        self._lock = threading.RLock()
        
        # Statistics
        self._stats = {
            "total_requests": 0,
            "allowed_requests": 0,
            "denied_requests": 0,
            "by_limit": {},
        }
    
    def register_limit(self, limit_id: str, algorithm: str,
                      max_requests: int, window_seconds: int,
                      burst_size: int = 0,
                      key_prefix: str = "") -> str:
        """Register a rate limit configuration."""
        config = RateLimitConfig(
            limit_id=limit_id,
            algorithm=RateLimitAlgorithm(algorithm),
            max_requests=max_requests,
            window_seconds=window_seconds,
            burst_size=burst_size,
            key_prefix=key_prefix,
        )
        
        self._configs[limit_id] = config
        
        logger.info("Rate limit registered: %s (%s)", limit_id, algorithm)
        
        return limit_id
    
    def check_rate_limit(self, key: str, limit_id: str,
                        cost: int = 1) -> RateLimitResult:
        """Check if request is allowed under rate limit."""
        with self._lock:
            self._stats["total_requests"] += 1
            
            if limit_id not in self._configs:
                # No limit configured, allow
                return RateLimitResult(
                    allowed=True,
                    remaining=-1,
                    reset_at="",
                    limit=0,
                    key=key,
                )
            
            config = self._configs[limit_id]
            
            if not config.enabled:
                return RateLimitResult(
                    allowed=True,
                    remaining=config.max_requests,
                    reset_at="",
                    limit=config.max_requests,
                    key=key,
                )
            
            # Apply key prefix
            full_key = f"{config.key_prefix}:{key}" if config.key_prefix else key
            
            # Dispatch to algorithm
            if config.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
                result = self._check_token_bucket(full_key, config, cost)
            elif config.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
                result = self._check_sliding_window(full_key, config, cost)
            elif config.algorithm == RateLimitAlgorithm.FIXED_WINDOW:
                result = self._check_fixed_window(full_key, config, cost)
            elif config.algorithm == RateLimitAlgorithm.LEAKY_BUCKET:
                result = self._check_leaky_bucket(full_key, config, cost)
            else:
                result = RateLimitResult(
                    allowed=True,
                    remaining=config.max_requests,
                    reset_at="",
                    limit=config.max_requests,
                    key=key,
                )
            
            # Update stats
            if result.allowed:
                self._stats["allowed_requests"] += 1
            else:
                self._stats["denied_requests"] += 1
            
            by_limit = self._stats["by_limit"].get(limit_id, {"allowed": 0, "denied": 0})
            if result.allowed:
                by_limit["allowed"] += 1
            else:
                by_limit["denied"] += 1
            self._stats["by_limit"][limit_id] = by_limit
            
            return result
    
    def _check_token_bucket(self, key: str, config: RateLimitConfig,
                           cost: int) -> RateLimitResult:
        """Token bucket algorithm."""
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()
        
        # Calculate refill
        max_tokens = config.max_requests + config.burst_size
        refill_rate = config.max_requests / config.window_seconds
        
        if key not in self._token_buckets:
            # Initialize bucket
            self._token_buckets[key] = TokenBucket(
                tokens=float(max_tokens),
                last_update=now_str,
                max_tokens=max_tokens,
                refill_rate=refill_rate,
            )
        
        bucket = self._token_buckets[key]
        
        # Refill tokens based on elapsed time
        last_update = datetime.fromisoformat(bucket.last_update)
        elapsed = (now - last_update).total_seconds()
        new_tokens = min(bucket.tokens + elapsed * refill_rate, float(max_tokens))
        
        bucket.tokens = new_tokens
        bucket.last_update = now_str
        
        # Check if enough tokens
        if bucket.tokens >= cost:
            bucket.tokens -= cost
            remaining = int(bucket.tokens)
            
            # Calculate reset time (when bucket will be full)
            tokens_needed = max_tokens - bucket.tokens
            reset_seconds = tokens_needed / refill_rate if refill_rate > 0 else 0
            reset_at = (now + timedelta(seconds=reset_seconds)).isoformat()
            
            return RateLimitResult(
                allowed=True,
                remaining=remaining,
                reset_at=reset_at,
                limit=max_tokens,
                key=key,
            )
        else:
            # Not enough tokens
            tokens_needed = cost - bucket.tokens
            retry_seconds = tokens_needed / refill_rate if refill_rate > 0 else 1
            
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=now_str,
                retry_after_seconds=int(retry_seconds) + 1,
                limit=max_tokens,
                key=key,
            )
    
    def _check_sliding_window(self, key: str, config: RateLimitConfig,
                             cost: int) -> RateLimitResult:
        """Sliding window algorithm."""
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()
        window_start = (now - timedelta(seconds=config.window_seconds)).isoformat()
        
        if key not in self._sliding_windows:
            self._sliding_windows[key] = []
        
        # Remove old timestamps
        timestamps = self._sliding_windows[key]
        timestamps = [ts for ts in timestamps if ts >= window_start]
        self._sliding_windows[key] = timestamps
        
        current_count = len(timestamps)
        
        if current_count + cost <= config.max_requests:
            # Allow request
            for _ in range(cost):
                timestamps.append(now_str)
            self._sliding_windows[key] = timestamps
            
            remaining = config.max_requests - len(timestamps)
            
            # Reset is when oldest request expires
            if timestamps:
                oldest = datetime.fromisoformat(timestamps[0])
                reset_at = (oldest + timedelta(seconds=config.window_seconds)).isoformat()
            else:
                reset_at = (now + timedelta(seconds=config.window_seconds)).isoformat()
            
            return RateLimitResult(
                allowed=True,
                remaining=remaining,
                reset_at=reset_at,
                limit=config.max_requests,
                key=key,
            )
        else:
            # Deny request
            if timestamps:
                oldest = datetime.fromisoformat(timestamps[0])
                reset_at = (oldest + timedelta(seconds=config.window_seconds)).isoformat()
                retry_seconds = (oldest + timedelta(seconds=config.window_seconds) - now).total_seconds()
            else:
                reset_at = now_str
                retry_seconds = 1
            
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=reset_at,
                retry_after_seconds=max(1, int(retry_seconds) + 1),
                limit=config.max_requests,
                key=key,
            )
    
    def _check_fixed_window(self, key: str, config: RateLimitConfig,
                           cost: int) -> RateLimitResult:
        """Fixed window algorithm."""
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()
        
        # Calculate window boundaries
        window_seconds = config.window_seconds
        current_window = int(now.timestamp() // window_seconds)
        window_start_ts = current_window * window_seconds
        window_start = datetime.fromtimestamp(window_start_ts, tz=timezone.utc).isoformat()
        window_end = datetime.fromtimestamp(window_start_ts + window_seconds, tz=timezone.utc).isoformat()
        
        window_key = f"{key}:{current_window}"
        
        if window_key not in self._fixed_windows:
            self._fixed_windows[window_key] = WindowState(
                count=0,
                window_start=window_start,
                window_seconds=window_seconds,
            )
        
        state = self._fixed_windows[window_key]
        
        # Check if we're in a new window
        if state.window_start != window_start:
            state.count = 0
            state.window_start = window_start
        
        if state.count + cost <= config.max_requests:
            state.count += cost
            remaining = config.max_requests - state.count
            
            return RateLimitResult(
                allowed=True,
                remaining=remaining,
                reset_at=window_end,
                limit=config.max_requests,
                key=key,
            )
        else:
            retry_seconds = (datetime.fromisoformat(window_end) - now).total_seconds()
            
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=window_end,
                retry_after_seconds=max(1, int(retry_seconds) + 1),
                limit=config.max_requests,
                key=key,
            )
    
    def _check_leaky_bucket(self, key: str, config: RateLimitConfig,
                           cost: int) -> RateLimitResult:
        """Leaky bucket algorithm."""
        now = datetime.now(timezone.utc)
        now_str = now.isoformat()
        
        max_water = config.max_requests
        leak_rate = config.max_requests / config.window_seconds
        
        if key not in self._leaky_buckets:
            self._leaky_buckets[key] = (0, now_str)
        
        water_level, last_update = self._leaky_buckets[key]
        
        # Leak water based on elapsed time
        last_update_dt = datetime.fromisoformat(last_update)
        elapsed = (now - last_update_dt).total_seconds()
        leaked = elapsed * leak_rate
        new_water_level = max(0, water_level - leaked)
        
        if new_water_level + cost <= max_water:
            # Allow request
            new_water_level += cost
            self._leaky_buckets[key] = (int(new_water_level), now_str)
            
            remaining = int(max_water - new_water_level)
            
            # Reset is when bucket empties
            empty_seconds = new_water_level / leak_rate if leak_rate > 0 else 0
            reset_at = (now + timedelta(seconds=empty_seconds)).isoformat()
            
            return RateLimitResult(
                allowed=True,
                remaining=remaining,
                reset_at=reset_at,
                limit=config.max_requests,
                key=key,
            )
        else:
            # Deny request
            self._leaky_buckets[key] = (int(new_water_level), now_str)
            
            # Retry when enough water has leaked
            excess = new_water_level + cost - max_water
            retry_seconds = excess / leak_rate if leak_rate > 0 else 1
            
            return RateLimitResult(
                allowed=False,
                remaining=0,
                reset_at=now_str,
                retry_after_seconds=max(1, int(retry_seconds) + 1),
                limit=config.max_requests,
                key=key,
            )
    
    def consume(self, key: str, limit_id: str, cost: int = 1) -> bool:
        """Consume rate limit quota. Returns True if allowed."""
        result = self.check_rate_limit(key, limit_id, cost)
        return result.allowed
    
    def get_remaining(self, key: str, limit_id: str) -> int:
        """Get remaining requests for a key."""
        result = self.check_rate_limit(key, limit_id, cost=0)
        return result.remaining
    
    def reset_limit(self, key: str, limit_id: str) -> bool:
        """Reset rate limit for a key."""
        with self._lock:
            if limit_id not in self._configs:
                return False
            
            config = self._configs[limit_id]
            full_key = f"{config.key_prefix}:{key}" if config.key_prefix else key
            
            # Clear state based on algorithm
            if config.algorithm == RateLimitAlgorithm.TOKEN_BUCKET:
                if full_key in self._token_buckets:
                    del self._token_buckets[full_key]
            elif config.algorithm == RateLimitAlgorithm.SLIDING_WINDOW:
                if full_key in self._sliding_windows:
                    del self._sliding_windows[full_key]
            elif config.algorithm == RateLimitAlgorithm.FIXED_WINDOW:
                # Clear all windows for this key
                keys_to_remove = [k for k in self._fixed_windows if k.startswith(f"{full_key}:")]
                for k in keys_to_remove:
                    del self._fixed_windows[k]
            elif config.algorithm == RateLimitAlgorithm.LEAKY_BUCKET:
                if full_key in self._leaky_buckets:
                    del self._leaky_buckets[full_key]
            
            return True
    
    def get_limit_config(self, limit_id: str) -> Optional[Dict[str, Any]]:
        """Get rate limit configuration."""
        if limit_id not in self._configs:
            return None
        
        return self._configs[limit_id].to_dict()
    
    def get_all_limits(self) -> List[Dict[str, Any]]:
        """Get all rate limit configurations."""
        return [c.to_dict() for c in self._configs.values()]
    
    def enable_limit(self, limit_id: str) -> bool:
        """Enable a rate limit."""
        if limit_id not in self._configs:
            return False
        
        self._configs[limit_id].enabled = True
        return True
    
    def disable_limit(self, limit_id: str) -> bool:
        """Disable a rate limit."""
        if limit_id not in self._configs:
            return False
        
        self._configs[limit_id].enabled = False
        return True
    
    def get_statistics(self) -> Dict[str, Any]:
        """Get rate limiting statistics."""
        return {
            **self._stats,
            "active_limits": len(self._configs),
            "token_buckets": len(self._token_buckets),
            "sliding_windows": len(self._sliding_windows),
            "fixed_windows": len(self._fixed_windows),
            "leaky_buckets": len(self._leaky_buckets),
        }
    
    def cleanup_old_state(self, older_than: Optional[str] = None) -> int:
        """Clean up old rate limit state."""
        with self._lock:
            removed = 0
            now = datetime.now(timezone.utc)
            
            if older_than:
                cutoff = datetime.fromisoformat(older_than)
            else:
                # Default: clean up state older than max window
                max_window = max((c.window_seconds for c in self._configs.values()), default=3600)
                cutoff = now - timedelta(seconds=max_window * 2)
            
            # Clean sliding windows
            for key, timestamps in list(self._sliding_windows.items()):
                old_timestamps = [ts for ts in timestamps if datetime.fromisoformat(ts) >= cutoff]
                if not old_timestamps:
                    del self._sliding_windows[key]
                    removed += 1
                elif len(old_timestamps) < len(timestamps):
                    self._sliding_windows[key] = old_timestamps
                    removed += len(timestamps) - len(old_timestamps)
            
            # Clean fixed windows
            keys_to_remove = [
                k for k in self._fixed_windows
                if datetime.fromisoformat(self._fixed_windows[k].window_start) < cutoff
            ]
            for k in keys_to_remove:
                del self._fixed_windows[k]
                removed += 1
            
            return removed
    
    def clear_all_state(self) -> int:
        """Clear all rate limit state."""
        with self._lock:
            count = (
                len(self._token_buckets) +
                len(self._sliding_windows) +
                len(self._fixed_windows) +
                len(self._leaky_buckets)
            )
            
            self._token_buckets.clear()
            self._sliding_windows.clear()
            self._fixed_windows.clear()
            self._leaky_buckets.clear()
            
            return count


def create_rate_limiter_engine() -> RateLimiterEngine:
    """Factory function to create rate limiter engine."""
    return RateLimiterEngine()
