"""Tests for Rate Limiter Advanced Engine — Slice 58."""
import pytest
from copilot_core.ratelimiter_advanced.engine import (
    RateLimiterEngine,
    Algorithm,
    LimitScope,
    RateLimitResult,
    RateLimitConfig,
    TokenBucket,
    SlidingWindowLog,
    FixedWindow,
    LeakyBucket,
    create_rate_limiter_engine,
)
from datetime import datetime, timezone, timedelta
import time


class TestTokenBucket:
    """Test token bucket algorithm."""
    
    def test_create_bucket(self):
        """Test creating token bucket."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        
        assert bucket.capacity == 10
        assert bucket.refill_rate == 1.0
        assert bucket.tokens == 10
    
    def test_acquire_success(self):
        """Test successful token acquisition."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        
        allowed, wait = bucket.acquire(1)
        
        assert allowed is True
        assert wait == 0.0
    
    def test_acquire_multiple(self):
        """Test acquiring multiple tokens."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        
        allowed, wait = bucket.acquire(5)
        
        assert allowed is True
        assert bucket.get_remaining() == 5
    
    def test_acquire_exceeds_capacity(self):
        """Test acquiring more than capacity."""
        bucket = TokenBucket(capacity=5, refill_rate=1.0)
        
        allowed, wait = bucket.acquire(10)
        
        assert allowed is False
        assert wait > 0
    
    def test_acquire_exhausts_bucket(self):
        """Test exhausting token bucket."""
        bucket = TokenBucket(capacity=3, refill_rate=1.0)
        
        bucket.acquire(3)
        
        allowed, wait = bucket.acquire(1)
        
        assert allowed is False
        assert wait > 0
    
    def test_refill_over_time(self):
        """Test token refill over time."""
        bucket = TokenBucket(capacity=10, refill_rate=10.0)  # 10 tokens/sec
        
        # Exhaust bucket
        bucket.acquire(10)
        
        # Wait for refill
        time.sleep(0.5)  # Should refill ~5 tokens
        
        allowed, wait = bucket.acquire(1)
        
        assert allowed is True
    
    def test_get_remaining(self):
        """Test getting remaining tokens."""
        bucket = TokenBucket(capacity=10, refill_rate=1.0)
        
        bucket.acquire(3)
        
        assert bucket.get_remaining() == 7
    
    def test_capacity_limit(self):
        """Test that tokens don't exceed capacity."""
        bucket = TokenBucket(capacity=5, refill_rate=100.0)
        
        # Wait for potential over-refill
        time.sleep(0.1)
        
        assert bucket.get_remaining() <= 5


class TestSlidingWindowLog:
    """Test sliding window log algorithm."""
    
    def test_create_window(self):
        """Test creating sliding window."""
        window = SlidingWindowLog(limit=10, window_seconds=60)
        
        assert window.limit == 10
        assert window.window_seconds == 60
    
    def test_acquire_success(self):
        """Test successful acquisition."""
        window = SlidingWindowLog(limit=5, window_seconds=60)
        
        allowed, remaining = window.acquire()
        
        assert allowed is True
        assert remaining == 4
    
    def test_acquire_exceeds_limit(self):
        """Test exceeding limit."""
        window = SlidingWindowLog(limit=3, window_seconds=60)
        
        window.acquire()
        window.acquire()
        window.acquire()
        
        allowed, remaining = window.acquire()
        
        assert allowed is False
        assert remaining == 0
    
    def test_window_expires(self):
        """Test window expiration."""
        window = SlidingWindowLog(limit=2, window_seconds=1)
        
        window.acquire()
        window.acquire()
        
        # Wait for window to expire
        time.sleep(1.1)
        
        allowed, remaining = window.acquire()
        
        assert allowed is True
    
    def test_get_remaining(self):
        """Test getting remaining requests."""
        window = SlidingWindowLog(limit=10, window_seconds=60)
        
        window.acquire()
        window.acquire()
        window.acquire()
        
        assert window.get_remaining() == 7


class TestFixedWindow:
    """Test fixed window algorithm."""
    
    def test_create_window(self):
        """Test creating fixed window."""
        window = FixedWindow(limit=10, window_seconds=60)
        
        assert window.limit == 10
        assert window.window_seconds == 60
    
    def test_acquire_success(self):
        """Test successful acquisition."""
        window = FixedWindow(limit=5, window_seconds=60)
        
        allowed, remaining, reset = window.acquire()
        
        assert allowed is True
        assert remaining == 4
    
    def test_acquire_exceeds_limit(self):
        """Test exceeding limit."""
        window = FixedWindow(limit=3, window_seconds=60)
        
        window.acquire()
        window.acquire()
        window.acquire()
        
        allowed, remaining, reset = window.acquire()
        
        assert allowed is False
        assert remaining == 0
    
    def test_window_resets(self):
        """Test window reset after expiration."""
        window = FixedWindow(limit=2, window_seconds=1)
        
        window.acquire()
        window.acquire()
        
        # Wait for window to reset
        time.sleep(1.1)
        
        allowed, remaining, reset = window.acquire()
        
        assert allowed is True
        assert remaining == 1
    
    def test_get_remaining(self):
        """Test getting remaining requests."""
        window = FixedWindow(limit=10, window_seconds=60)
        
        window.acquire()
        window.acquire()
        
        assert window.get_remaining() == 8


class TestLeakyBucket:
    """Test leaky bucket algorithm."""
    
    def test_create_bucket(self):
        """Test creating leaky bucket."""
        bucket = LeakyBucket(capacity=10, leak_rate=1.0)
        
        assert bucket.capacity == 10
        assert bucket.leak_rate == 1.0
    
    def test_acquire_success(self):
        """Test successful acquisition."""
        bucket = LeakyBucket(capacity=10, leak_rate=1.0)
        
        allowed, wait = bucket.acquire()
        
        assert allowed is True
        assert wait == 0.0
    
    def test_acquire_exceeds_capacity(self):
        """Test exceeding capacity."""
        bucket = LeakyBucket(capacity=3, leak_rate=1.0)
        
        bucket.acquire()
        bucket.acquire()
        bucket.acquire()
        
        allowed, wait = bucket.acquire()
        
        assert allowed is False
        assert wait > 0
    
    def test_leak_over_time(self):
        """Test water leaking over time."""
        bucket = LeakyBucket(capacity=5, leak_rate=10.0)  # 10 requests/sec
        
        # Fill bucket
        for _ in range(5):
            bucket.acquire()
        
        # Wait for leak
        time.sleep(0.5)  # Should leak ~5 requests
        
        allowed, wait = bucket.acquire()
        
        assert allowed is True
    
    def test_get_remaining(self):
        """Test getting remaining capacity."""
        bucket = LeakyBucket(capacity=10, leak_rate=1.0)
        
        bucket.acquire()
        bucket.acquire()
        bucket.acquire()
        
        assert bucket.get_remaining() == 7


class TestRateLimiterEngine:
    """Test rate limiter engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_rate_limiter_engine()
        assert engine is not None
    
    def test_create_config_token_bucket(self):
        """Test creating token bucket config."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="API Limit",
            algorithm=Algorithm.TOKEN_BUCKET,
            limit=100,
            window_seconds=60,
        )
        
        assert config_id is not None
        assert config_id.startswith("rlc_")
        
        config = engine.get_config(config_id)
        
        assert config.name == "API Limit"
        assert config.algorithm == Algorithm.TOKEN_BUCKET
        assert config.limit == 100
    
    def test_create_config_sliding_window(self):
        """Test creating sliding window config."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="Sliding Limit",
            algorithm=Algorithm.SLIDING_WINDOW,
            limit=50,
            window_seconds=60,
        )
        
        config = engine.get_config(config_id)
        
        assert config.algorithm == Algorithm.SLIDING_WINDOW
    
    def test_create_config_fixed_window(self):
        """Test creating fixed window config."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="Fixed Limit",
            algorithm=Algorithm.FIXED_WINDOW,
            limit=100,
            window_seconds=60,
        )
        
        config = engine.get_config(config_id)
        
        assert config.algorithm == Algorithm.FIXED_WINDOW
    
    def test_create_config_leaky_bucket(self):
        """Test creating leaky bucket config."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="Leaky Limit",
            algorithm=Algorithm.LEAKY_BUCKET,
            limit=100,
            window_seconds=60,
        )
        
        config = engine.get_config(config_id)
        
        assert config.algorithm == Algorithm.LEAKY_BUCKET
    
    def test_create_config_with_burst(self):
        """Test creating config with burst limit."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="Burst Limit",
            algorithm=Algorithm.TOKEN_BUCKET,
            limit=100,
            window_seconds=60,
            burst_limit=200,
        )
        
        config = engine.get_config(config_id)
        
        assert config.burst_limit == 200
    
    def test_create_config_with_scope(self):
        """Test creating config with scope."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="User Limit",
            algorithm=Algorithm.TOKEN_BUCKET,
            limit=100,
            window_seconds=60,
            scope=LimitScope.USER,
        )
        
        config = engine.get_config(config_id)
        
        assert config.scope == LimitScope.USER
    
    def test_update_config(self):
        """Test updating config."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="Test",
            algorithm=Algorithm.TOKEN_BUCKET,
            limit=100,
            window_seconds=60,
        )
        
        result = engine.update_config(
            config_id,
            limit=200,
            window_seconds=120,
        )
        
        assert result is True
        
        config = engine.get_config(config_id)
        
        assert config.limit == 200
        assert config.window_seconds == 120
    
    def test_update_nonexistent_config(self):
        """Test updating nonexistent config."""
        engine = RateLimiterEngine()
        
        result = engine.update_config("nonexistent", limit=200)
        
        assert result is False
    
    def test_delete_config(self):
        """Test deleting config."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config("Test", Algorithm.TOKEN_BUCKET, 100, 60)
        
        result = engine.delete_config(config_id)
        
        assert result is True
        assert engine.get_config(config_id) is None
    
    def test_delete_nonexistent_config(self):
        """Test deleting nonexistent config."""
        engine = RateLimiterEngine()
        
        result = engine.delete_config("nonexistent")
        
        assert result is False
    
    def test_get_config(self):
        """Test getting config."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config("Test", Algorithm.TOKEN_BUCKET, 100, 60)
        
        config = engine.get_config(config_id)
        
        assert config is not None
        assert config.name == "Test"
    
    def test_get_nonexistent_config(self):
        """Test getting nonexistent config."""
        engine = RateLimiterEngine()
        
        config = engine.get_config("nonexistent")
        
        assert config is None
    
    def test_list_configs(self):
        """Test listing configs."""
        engine = RateLimiterEngine()
        
        engine.create_config("Config 1", Algorithm.TOKEN_BUCKET, 100, 60)
        engine.create_config("Config 2", Algorithm.SLIDING_WINDOW, 50, 60)
        engine.create_config("Config 3", Algorithm.FIXED_WINDOW, 100, 60)
        
        configs = engine.list_configs()
        
        assert len(configs) == 3
    
    def test_check_allowed(self):
        """Test check that allows request."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="Test",
            algorithm=Algorithm.TOKEN_BUCKET,
            limit=10,
            window_seconds=60,
        )
        
        result = engine.check(config_id, "user_123")
        
        assert result.allowed is True
        assert result.limit == 10
        assert result.remaining == 9
    
    def test_check_denied(self):
        """Test check that denies request."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="Test",
            algorithm=Algorithm.FIXED_WINDOW,
            limit=2,
            window_seconds=60,
        )
        
        # Exhaust limit
        engine.check(config_id, "user_123")
        engine.check(config_id, "user_123")
        
        result = engine.check(config_id, "user_123")
        
        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after is not None
    
    def test_check_disabled_config(self):
        """Test check with disabled config."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="Test",
            algorithm=Algorithm.TOKEN_BUCKET,
            limit=10,
            window_seconds=60,
        )
        
        engine.update_config(config_id, enabled=False)
        
        result = engine.check(config_id, "user_123")
        
        assert result.allowed is True
        assert result.limit == 0  # Disabled
    
    def test_check_nonexistent_config(self):
        """Test check with nonexistent config."""
        engine = RateLimiterEngine()
        
        result = engine.check("nonexistent", "user_123")
        
        assert result.allowed is True
    
    def test_check_different_keys(self):
        """Test check with different keys."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="Test",
            algorithm=Algorithm.FIXED_WINDOW,
            limit=2,
            window_seconds=60,
        )
        
        # Exhaust for user1
        engine.check(config_id, "user1")
        engine.check(config_id, "user1")
        
        # user2 should still be allowed
        result = engine.check(config_id, "user2")
        
        assert result.allowed is True
    
    def test_reset_key(self):
        """Test resetting specific key."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="Test",
            algorithm=Algorithm.FIXED_WINDOW,
            limit=2,
            window_seconds=60,
        )
        
        # Exhaust limit
        engine.check(config_id, "user_123")
        engine.check(config_id, "user_123")
        
        # Reset key
        result = engine.reset_key(config_id, "user_123")
        
        assert result is True
        
        # Should be allowed again
        check_result = engine.check(config_id, "user_123")
        
        assert check_result.allowed is True
    
    def test_reset_nonexistent_key(self):
        """Test resetting nonexistent key."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config("Test", Algorithm.TOKEN_BUCKET, 10, 60)
        
        result = engine.reset_key(config_id, "nonexistent")
        
        assert result is False
    
    def test_reset_all(self):
        """Test resetting all keys."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="Test",
            algorithm=Algorithm.FIXED_WINDOW,
            limit=2,
            window_seconds=60,
        )
        
        # Create multiple keys
        for i in range(5):
            engine.check(config_id, f"user_{i}")
        
        count = engine.reset_all(config_id)
        
        assert count == 5
        
        # All keys should be reset
        for i in range(5):
            result = engine.check(config_id, f"user_{i}")
            assert result.allowed is True
    
    def test_reset_all_nonexistent_config(self):
        """Test resetting all for nonexistent config."""
        engine = RateLimiterEngine()
        
        count = engine.reset_all("nonexistent")
        
        assert count == 0
    
    def test_get_key_status(self):
        """Test getting key status."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="Test",
            algorithm=Algorithm.TOKEN_BUCKET,
            limit=10,
            window_seconds=60,
        )
        
        engine.check(config_id, "user_123")
        
        status = engine.get_key_status(config_id, "user_123")
        
        assert status is not None
        assert status["key"] == "user_123"
        assert status["limit"] == 10
    
    def test_get_key_status_nonexistent(self):
        """Test getting status for nonexistent key."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config("Test", Algorithm.TOKEN_BUCKET, 10, 60)
        
        status = engine.get_key_status(config_id, "nonexistent")
        
        assert status is None
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config("Test", Algorithm.TOKEN_BUCKET, 10, 60)
        
        for i in range(5):
            engine.check(config_id, f"user_{i}")
        
        stats = engine.get_statistics()
        
        assert stats["total_requests"] == 5
        assert stats["total_configs"] == 1
    
    def test_statistics_by_config(self):
        """Test statistics by config."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config("Test", Algorithm.TOKEN_BUCKET, 10, 60)
        
        for i in range(10):
            engine.check(config_id, "user_123")
        
        stats = engine.get_statistics()
        
        assert stats["by_config"][config_id] == 10
    
    def test_statistics_by_key(self):
        """Test statistics by key."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config("Test", Algorithm.TOKEN_BUCKET, 10, 60)
        
        for i in range(5):
            engine.check(config_id, "user_123")
        
        stats = engine.get_statistics()
        
        assert stats["by_key"]["user_123"] == 5
    
    def test_clear(self):
        """Test clearing all configs."""
        engine = RateLimiterEngine()
        
        engine.create_config("Config 1", Algorithm.TOKEN_BUCKET, 10, 60)
        engine.create_config("Config 2", Algorithm.SLIDING_WINDOW, 10, 60)
        
        count = engine.clear()
        
        assert count == 2
        assert len(engine.list_configs()) == 0
    
    def test_rate_limit_result_to_dict(self):
        """Test rate limit result serialization."""
        result = RateLimitResult(
            allowed=True,
            limit=100,
            remaining=95,
            reset_at="2025-01-01T00:00:00Z",
            retry_after=None,
            key="user_123",
        )
        
        d = result.to_dict()
        
        assert d["allowed"] is True
        assert d["limit"] == 100
        assert d["remaining"] == 95
        assert d["key"] == "user_123"
    
    def test_rate_limit_config_to_dict(self):
        """Test rate limit config serialization."""
        config = RateLimitConfig(
            config_id="rlc_test",
            name="Test Config",
            algorithm=Algorithm.TOKEN_BUCKET,
            limit=100,
            window_seconds=60,
            burst_limit=200,
            scope=LimitScope.USER,
        )
        
        d = config.to_dict()
        
        assert d["config_id"] == "rlc_test"
        assert d["algorithm"] == "token_bucket"
        assert d["burst_limit"] == 200
    
    def test_algorithm_enum_values(self):
        """Test algorithm enum values."""
        assert Algorithm.TOKEN_BUCKET.value == "token_bucket"
        assert Algorithm.SLIDING_WINDOW.value == "sliding_window"
        assert Algorithm.FIXED_WINDOW.value == "fixed_window"
        assert Algorithm.LEAKY_BUCKET.value == "leaky_bucket"
    
    def test_limit_scope_enum_values(self):
        """Test limit scope enum values."""
        assert LimitScope.GLOBAL.value == "global"
        assert LimitScope.USER.value == "user"
        assert LimitScope.IP.value == "ip"
        assert LimitScope.API_KEY.value == "api_key"
        assert LimitScope.ENDPOINT.value == "endpoint"
    
    def test_config_created_at_set(self):
        """Test that config created_at is set."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config("Test", Algorithm.TOKEN_BUCKET, 10, 60)
        
        config = engine.get_config(config_id)
        
        assert config.created_at is not None
    
    def test_check_updates_statistics(self):
        """Test that check updates statistics."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config("Test", Algorithm.TOKEN_BUCKET, 10, 60)
        
        engine.check(config_id, "user_123")
        
        stats = engine.get_statistics()
        
        assert stats["total_requests"] == 1
        assert stats["allowed_requests"] == 1
    
    def test_check_denied_updates_statistics(self):
        """Test that denied check updates statistics."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="Test",
            algorithm=Algorithm.FIXED_WINDOW,
            limit=1,
            window_seconds=60,
        )
        
        engine.check(config_id, "user_123")
        engine.check(config_id, "user_123")  # Should be denied
        
        stats = engine.get_statistics()
        
        assert stats["denied_requests"] == 1
    
    def test_multiple_configs_independent(self):
        """Test that multiple configs are independent."""
        engine = RateLimiterEngine()
        
        config1 = engine.create_config("Config 1", Algorithm.FIXED_WINDOW, 2, 60)
        config2 = engine.create_config("Config 2", Algorithm.FIXED_WINDOW, 5, 60)
        
        # Exhaust config1
        engine.check(config1, "user_123")
        engine.check(config1, "user_123")
        
        result1 = engine.check(config1, "user_123")
        result2 = engine.check(config2, "user_123")
        
        assert result1.allowed is False
        assert result2.allowed is True
    
    def test_config_with_default_values(self):
        """Test config with default values."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config("Test", Algorithm.TOKEN_BUCKET, 10, 60)
        
        config = engine.get_config(config_id)
        
        assert config.burst_limit is None
        assert config.scope == LimitScope.GLOBAL
        assert config.enabled is True
    
    def test_disable_config(self):
        """Test disabling config."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config("Test", Algorithm.TOKEN_BUCKET, 10, 60)
        
        engine.update_config(config_id, enabled=False)
        
        config = engine.get_config(config_id)
        
        assert config.enabled is False
    
    def test_enable_disabled_config(self):
        """Test re-enabling disabled config."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config("Test", Algorithm.TOKEN_BUCKET, 10, 60)
        
        engine.update_config(config_id, enabled=False)
        engine.update_config(config_id, enabled=True)
        
        config = engine.get_config(config_id)
        
        assert config.enabled is True
    
    def test_config_id_unique(self):
        """Test that config IDs are unique."""
        engine = RateLimiterEngine()
        
        ids = set()
        for i in range(50):
            config_id = engine.create_config(f"Config {i}", Algorithm.TOKEN_BUCKET, 10, 60)
            ids.add(config_id)
        
        assert len(ids) == 50
    
    def test_check_with_empty_key(self):
        """Test check with empty key."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config("Test", Algorithm.TOKEN_BUCKET, 10, 60)
        
        result = engine.check(config_id, "")
        
        assert result.allowed is True
    
    def test_check_default_key(self):
        """Test check with default key."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config("Test", Algorithm.TOKEN_BUCKET, 10, 60)
        
        result = engine.check(config_id)
        
        assert result.allowed is True
        assert result.key == "default"
    
    def test_rate_limit_result_retry_after_on_deny(self):
        """Test that retry_after is set on denial."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="Test",
            algorithm=Algorithm.FIXED_WINDOW,
            limit=1,
            window_seconds=60,
        )
        
        engine.check(config_id, "user_123")
        
        result = engine.check(config_id, "user_123")
        
        assert result.allowed is False
        assert result.retry_after is not None
        assert result.retry_after > 0
    
    def test_rate_limit_result_no_retry_after_on_allow(self):
        """Test that retry_after is None on allowance."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config("Test", Algorithm.TOKEN_BUCKET, 10, 60)
        
        result = engine.check(config_id, "user_123")
        
        assert result.allowed is True
        assert result.retry_after is None
    
    def test_sliding_window_reset_after_expiry(self):
        """Test sliding window resets after expiry."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="Test",
            algorithm=Algorithm.SLIDING_WINDOW,
            limit=2,
            window_seconds=1,
        )
        
        # Exhaust limit
        engine.check(config_id, "user_123")
        engine.check(config_id, "user_123")
        
        # Wait for window to expire
        time.sleep(1.1)
        
        # Should be allowed again
        result = engine.check(config_id, "user_123")
        
        assert result.allowed is True
    
    def test_fixed_window_reset_after_expiry(self):
        """Test fixed window resets after expiry."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="Test",
            algorithm=Algorithm.FIXED_WINDOW,
            limit=2,
            window_seconds=1,
        )
        
        # Exhaust limit
        engine.check(config_id, "user_123")
        engine.check(config_id, "user_123")
        
        # Wait for window to reset
        time.sleep(1.1)
        
        # Should be allowed again
        result = engine.check(config_id, "user_123")
        
        assert result.allowed is True
    
    def test_token_bucket_refill_continuous(self):
        """Test token bucket refills continuously."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="Test",
            algorithm=Algorithm.TOKEN_BUCKET,
            limit=10,
            window_seconds=1,  # 10 tokens/sec
            burst_limit=10,
        )
        
        # Exhaust burst
        for _ in range(10):
            engine.check(config_id, "user_123")
        
        # Wait for partial refill
        time.sleep(0.5)
        
        # Should have ~5 tokens refilled
        result = engine.check(config_id, "user_123")
        
        assert result.allowed is True
    
    def test_leaky_bucket_continuous_processing(self):
        """Test leaky bucket allows continuous processing."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="Test",
            algorithm=Algorithm.LEAKY_BUCKET,
            limit=10,
            window_seconds=1,  # 10 requests/sec
            burst_limit=10,
        )
        
        # Should allow steady stream
        allowed_count = 0
        for _ in range(15):
            result = engine.check(config_id, "user_123")
            if result.allowed:
                allowed_count += 1
            time.sleep(0.05)  # Small delay
        
        # Should have allowed most requests (leak rate)
        assert allowed_count >= 10
    
    def test_get_statistics_total_keys(self):
        """Test that statistics track total keys."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config("Test", Algorithm.TOKEN_BUCKET, 10, 60)
        
        for i in range(5):
            engine.check(config_id, f"user_{i}")
        
        stats = engine.get_statistics()
        
        assert stats["total_keys"] == 5
    
    def test_clear_empty_engine(self):
        """Test clearing empty engine."""
        engine = RateLimiterEngine()
        
        count = engine.clear()
        
        assert count == 0
    
    def test_list_configs_empty(self):
        """Test listing configs when empty."""
        engine = RateLimiterEngine()
        
        configs = engine.list_configs()
        
        assert configs == []
    
    def test_update_burst_limit(self):
        """Test updating burst limit."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="Test",
            algorithm=Algorithm.TOKEN_BUCKET,
            limit=10,
            window_seconds=60,
            burst_limit=20,
        )
        
        engine.update_config(config_id, burst_limit=50)
        
        config = engine.get_config(config_id)
        
        assert config.burst_limit == 50
    
    def test_check_reset_at_formatted(self):
        """Test that reset_at is properly formatted."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config("Test", Algorithm.TOKEN_BUCKET, 10, 60)
        
        result = engine.check(config_id, "user_123")
        
        assert result.reset_at is not None
        # Should be ISO format
        assert "T" in result.reset_at
    
    def test_multiple_algorithms_same_engine(self):
        """Test multiple algorithms in same engine."""
        engine = RateLimiterEngine()
        
        token_config = engine.create_config("Token", Algorithm.TOKEN_BUCKET, 10, 60)
        sliding_config = engine.create_config("Sliding", Algorithm.SLIDING_WINDOW, 10, 60)
        fixed_config = engine.create_config("Fixed", Algorithm.FIXED_WINDOW, 10, 60)
        leaky_config = engine.create_config("Leaky", Algorithm.LEAKY_BUCKET, 10, 60)
        
        # All should work
        for config_id in [token_config, sliding_config, fixed_config, leaky_config]:
            result = engine.check(config_id, "user_123")
            assert result.allowed is True
    
    def test_config_name_unique_not_required(self):
        """Test that config names don't need to be unique."""
        engine = RateLimiterEngine()
        
        config1 = engine.create_config("Same Name", Algorithm.TOKEN_BUCKET, 10, 60)
        config2 = engine.create_config("Same Name", Algorithm.SLIDING_WINDOW, 10, 60)
        
        # Both should exist with different IDs
        assert config1 != config2
        assert engine.get_config(config1) is not None
        assert engine.get_config(config2) is not None
    
    def test_statistics_initial_values(self):
        """Test statistics initial values."""
        engine = RateLimiterEngine()
        
        stats = engine.get_statistics()
        
        assert stats["total_requests"] == 0
        assert stats["allowed_requests"] == 0
        assert stats["denied_requests"] == 0
        assert stats["total_configs"] == 0
        assert stats["total_keys"] == 0
    
    def test_key_status_algorithm(self):
        """Test that key status includes algorithm."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config("Test", Algorithm.SLIDING_WINDOW, 10, 60)
        
        engine.check(config_id, "user_123")
        
        status = engine.get_key_status(config_id, "user_123")
        
        assert status["algorithm"] == "sliding_window"
    
    def test_key_status_window_seconds(self):
        """Test that key status includes window_seconds."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config("Test", Algorithm.TOKEN_BUCKET, 10, 120)
        
        engine.check(config_id, "user_123")
        
        status = engine.get_key_status(config_id, "user_123")
        
        assert status["window_seconds"] == 120
    
    def test_check_handles_rapid_requests(self):
        """Test handling rapid requests."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="Test",
            algorithm=Algorithm.FIXED_WINDOW,
            limit=100,
            window_seconds=60,
        )
        
        # Rapid fire requests
        results = []
        for _ in range(150):
            result = engine.check(config_id, "user_123")
            results.append(result.allowed)
        
        # First 100 should be allowed, rest denied
        assert results.count(True) == 100
        assert results.count(False) == 50
    
    def test_different_scopes_same_config(self):
        """Test different scopes with same config."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="Test",
            algorithm=Algorithm.FIXED_WINDOW,
            limit=2,
            window_seconds=60,
            scope=LimitScope.USER,
        )
        
        # Different users should have independent limits
        engine.check(config_id, "user1")
        engine.check(config_id, "user1")
        
        result1 = engine.check(config_id, "user1")
        result2 = engine.check(config_id, "user2")
        
        assert result1.allowed is False
        assert result2.allowed is True
    
    def test_burst_allows_initial_spike(self):
        """Test that burst allows initial spike."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config(
            name="Test",
            algorithm=Algorithm.TOKEN_BUCKET,
            limit=10,
            window_seconds=60,
            burst_limit=50,
        )
        
        # Should allow burst
        allowed_count = 0
        for _ in range(50):
            result = engine.check(config_id, "user_123")
            if result.allowed:
                allowed_count += 1
        
        assert allowed_count == 50
    
    def test_reset_at_in_future(self):
        """Test that reset_at is in the future."""
        engine = RateLimiterEngine()
        
        config_id = engine.create_config("Test", Algorithm.TOKEN_BUCKET, 10, 60)
        
        result = engine.check(config_id, "user_123")
        
        reset = datetime.fromisoformat(result.reset_at.replace('Z', '+00:00'))
        now = datetime.now(timezone.utc)
        
        assert reset >= now
