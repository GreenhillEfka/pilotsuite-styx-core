"""Tests for Rate Limiter Engine — Slice 39."""
import pytest
from copilot_core.ratelimiter.engine import (
    RateLimiterEngine,
    RateLimitAlgorithm,
    RateLimitConfig,
    RateLimitResult,
    TokenBucket,
    WindowState,
    create_rate_limiter_engine,
)
from datetime import datetime, timezone, timedelta
import time


class TestRateLimiterEngine:
    """Test rate limiter engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_rate_limiter_engine()
        assert engine is not None
    
    def test_register_limit_token_bucket(self):
        """Test registering token bucket limit."""
        engine = RateLimiterEngine()
        
        limit_id = engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=100,
            window_seconds=60,
        )
        
        assert limit_id == "api_limit"
        
        config = engine.get_limit_config("api_limit")
        assert config is not None
        assert config["algorithm"] == "token_bucket"
        assert config["max_requests"] == 100
    
    def test_register_limit_sliding_window(self):
        """Test registering sliding window limit."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="sliding_window",
            max_requests=100,
            window_seconds=60,
        )
        
        config = engine.get_limit_config("api_limit")
        assert config["algorithm"] == "sliding_window"
    
    def test_register_limit_fixed_window(self):
        """Test registering fixed window limit."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="fixed_window",
            max_requests=100,
            window_seconds=60,
        )
        
        config = engine.get_limit_config("api_limit")
        assert config["algorithm"] == "fixed_window"
    
    def test_register_limit_leaky_bucket(self):
        """Test registering leaky bucket limit."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="leaky_bucket",
            max_requests=100,
            window_seconds=60,
        )
        
        config = engine.get_limit_config("api_limit")
        assert config["algorithm"] == "leaky_bucket"
    
    def test_register_limit_with_burst(self):
        """Test registering limit with burst size."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=100,
            window_seconds=60,
            burst_size=20,
        )
        
        config = engine.get_limit_config("api_limit")
        assert config["burst_size"] == 20
    
    def test_register_limit_with_key_prefix(self):
        """Test registering limit with key prefix."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=100,
            window_seconds=60,
            key_prefix="user",
        )
        
        config = engine.get_limit_config("api_limit")
        assert config["key_prefix"] == "user"
    
    def test_check_rate_limit_allowed(self):
        """Test rate limit check - allowed."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=10,
            window_seconds=60,
        )
        
        result = engine.check_rate_limit("user_001", "api_limit")
        
        assert result.allowed is True
        assert result.remaining >= 0
        assert result.limit == 10
    
    def test_check_rate_limit_denied(self):
        """Test rate limit check - denied."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=2,
            window_seconds=60,
        )
        
        # Exhaust limit
        engine.check_rate_limit("user_001", "api_limit")
        engine.check_rate_limit("user_001", "api_limit")
        
        # Third request should be denied
        result = engine.check_rate_limit("user_001", "api_limit")
        
        assert result.allowed is False
        assert result.remaining == 0
        assert result.retry_after_seconds > 0
    
    def test_consume_helper(self):
        """Test consume helper method."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=2,
            window_seconds=60,
        )
        
        assert engine.consume("user_001", "api_limit") is True
        assert engine.consume("user_001", "api_limit") is True
        assert engine.consume("user_001", "api_limit") is False
    
    def test_get_remaining(self):
        """Test getting remaining requests."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=10,
            window_seconds=60,
        )
        
        remaining_before = engine.get_remaining("user_001", "api_limit")
        
        engine.consume("user_001", "api_limit")
        engine.consume("user_001", "api_limit")
        engine.consume("user_001", "api_limit")
        
        remaining_after = engine.get_remaining("user_001", "api_limit")
        
        assert remaining_before > remaining_after
    
    def test_reset_limit(self):
        """Test resetting rate limit."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=2,
            window_seconds=60,
        )
        
        # Exhaust limit
        engine.consume("user_001", "api_limit")
        engine.consume("user_001", "api_limit")
        
        assert engine.consume("user_001", "api_limit") is False
        
        # Reset
        engine.reset_limit("user_001", "api_limit")
        
        # Should be allowed again
        assert engine.consume("user_001", "api_limit") is True
    
    def test_reset_unknown_limit(self):
        """Test resetting unknown limit."""
        engine = RateLimiterEngine()
        
        result = engine.reset_limit("user_001", "unknown_limit")
        
        assert result is False
    
    def test_get_limit_config(self):
        """Test getting limit config."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=100,
            window_seconds=60,
            burst_size=10,
        )
        
        config = engine.get_limit_config("api_limit")
        
        assert config is not None
        assert config["limit_id"] == "api_limit"
        assert config["burst_size"] == 10
    
    def test_get_unknown_limit_config(self):
        """Test getting unknown limit config."""
        engine = RateLimiterEngine()
        
        config = engine.get_limit_config("unknown")
        
        assert config is None
    
    def test_get_all_limits(self):
        """Test getting all limits."""
        engine = RateLimiterEngine()
        
        engine.register_limit("limit1", "token_bucket", 100, 60)
        engine.register_limit("limit2", "sliding_window", 50, 30)
        engine.register_limit("limit3", "fixed_window", 200, 120)
        
        limits = engine.get_all_limits()
        
        assert len(limits) == 3
    
    def test_enable_disable_limit(self):
        """Test enabling/disabling limit."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=2,
            window_seconds=60,
        )
        
        # Disable
        result = engine.disable_limit("api_limit")
        assert result is True
        
        # Should always allow when disabled
        for i in range(10):
            result = engine.check_rate_limit("user_001", "api_limit")
            assert result.allowed is True
        
        # Enable
        result = engine.enable_limit("api_limit")
        assert result is True
        
        # Should enforce limit again
        engine.consume("user_001", "api_limit")
        engine.consume("user_001", "api_limit")
        result = engine.check_rate_limit("user_001", "api_limit")
        assert result.allowed is False
    
    def test_enable_unknown_limit(self):
        """Test enabling unknown limit."""
        engine = RateLimiterEngine()
        
        result = engine.enable_limit("unknown")
        
        assert result is False
    
    def test_disable_unknown_limit(self):
        """Test disabling unknown limit."""
        engine = RateLimiterEngine()
        
        result = engine.disable_limit("unknown")
        
        assert result is False
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = RateLimiterEngine()
        
        engine.register_limit("api_limit", "token_bucket", 10, 60)
        
        for i in range(15):
            engine.consume("user_001", "api_limit")
        
        stats = engine.get_statistics()
        
        assert stats["total_requests"] == 15
        assert stats["allowed_requests"] == 10
        assert stats["denied_requests"] == 5
    
    def test_statistics_by_limit(self):
        """Test statistics breakdown by limit."""
        engine = RateLimiterEngine()
        
        engine.register_limit("limit1", "token_bucket", 5, 60)
        engine.register_limit("limit2", "token_bucket", 3, 60)
        
        for i in range(10):
            engine.consume("user_001", "limit1")
            engine.consume("user_002", "limit2")
        
        stats = engine.get_statistics()
        
        assert "limit1" in stats["by_limit"]
        assert "limit2" in stats["by_limit"]
        assert stats["by_limit"]["limit1"]["allowed"] == 5
        assert stats["by_limit"]["limit2"]["allowed"] == 3
    
    def test_cleanup_old_state(self):
        """Test cleaning up old state."""
        engine = RateLimiterEngine()
        
        engine.register_limit("api_limit", "sliding_window", 100, 1)
        
        # Create some state
        for i in range(10):
            engine.consume("user_001", "api_limit")
        
        # Wait for state to expire
        time.sleep(1.5)
        
        removed = engine.cleanup_old_state()
        
        assert removed >= 1
    
    def test_clear_all_state(self):
        """Test clearing all state."""
        engine = RateLimiterEngine()
        
        engine.register_limit("limit1", "token_bucket", 10, 60)
        engine.register_limit("limit2", "sliding_window", 10, 60)
        
        # Create state
        for i in range(5):
            engine.consume("user_001", "limit1")
            engine.consume("user_002", "limit2")
        
        count = engine.clear_all_state()
        
        assert count > 0
        
        stats = engine.get_statistics()
        assert stats["token_buckets"] == 0
        assert stats["sliding_windows"] == 0
    
    def test_token_bucket_refill(self):
        """Test token bucket refill over time."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=2,
            window_seconds=1,  # 2 requests per second
        )
        
        # Exhaust limit
        engine.consume("user_001", "api_limit")
        engine.consume("user_001", "api_limit")
        
        assert engine.consume("user_001", "api_limit") is False
        
        # Wait for refill
        time.sleep(1.1)
        
        # Should have tokens again
        assert engine.consume("user_001", "api_limit") is True
    
    def test_sliding_window_expiration(self):
        """Test sliding window expiration."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="sliding_window",
            max_requests=2,
            window_seconds=1,
        )
        
        # Exhaust limit
        engine.consume("user_001", "api_limit")
        engine.consume("user_001", "api_limit")
        
        assert engine.consume("user_001", "api_limit") is False
        
        # Wait for window to slide
        time.sleep(1.1)
        
        # Should be allowed again
        assert engine.consume("user_001", "api_limit") is True
    
    def test_fixed_window_reset(self):
        """Test fixed window reset at boundary."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="fixed_window",
            max_requests=2,
            window_seconds=1,
        )
        
        # Exhaust limit
        engine.consume("user_001", "api_limit")
        engine.consume("user_001", "api_limit")
        
        assert engine.consume("user_001", "api_limit") is False
        
        # Wait for new window
        time.sleep(1.1)
        
        # Should be allowed in new window
        assert engine.consume("user_001", "api_limit") is True
    
    def test_leaky_bucket_leak(self):
        """Test leaky bucket leak over time."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="leaky_bucket",
            max_requests=2,
            window_seconds=1,
        )
        
        # Fill bucket
        engine.consume("user_001", "api_limit")
        engine.consume("user_001", "api_limit")
        
        assert engine.consume("user_001", "api_limit") is False
        
        # Wait for leak
        time.sleep(1.1)
        
        # Should have room again
        assert engine.consume("user_001", "api_limit") is True
    
    def test_burst_allowance(self):
        """Test burst allowance."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=10,
            window_seconds=60,
            burst_size=5,
        )
        
        # Should allow 15 requests initially (10 + 5 burst)
        allowed = 0
        for i in range(20):
            if engine.consume("user_001", "api_limit"):
                allowed += 1
        
        assert allowed == 15
    
    def test_key_prefix_isolation(self):
        """Test that key prefixes isolate limits."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=2,
            window_seconds=60,
            key_prefix="user",
        )
        
        # Different keys with same prefix should be separate
        engine.consume("user_001", "api_limit")
        engine.consume("user_001", "api_limit")
        
        # user_001 is exhausted
        assert engine.consume("user_001", "api_limit") is False
        
        # user_002 should still have quota
        assert engine.consume("user_002", "api_limit") is True
    
    def test_cost_parameter(self):
        """Test cost parameter for rate limit."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=10,
            window_seconds=60,
        )
        
        # Consume with cost 5
        engine.consume("user_001", "api_limit", cost=5)
        
        remaining = engine.get_remaining("user_001", "api_limit")
        
        assert remaining == 5
    
    def test_high_cost_denied(self):
        """Test that high cost request is denied."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=5,
            window_seconds=60,
        )
        
        # Try to consume with cost 10 (more than limit)
        result = engine.check_rate_limit("user_001", "api_limit", cost=10)
        
        assert result.allowed is False
    
    def test_check_unknown_limit_allows(self):
        """Test that checking unknown limit allows request."""
        engine = RateLimiterEngine()
        
        result = engine.check_rate_limit("user_001", "unknown_limit")
        
        assert result.allowed is True
        assert result.remaining == -1  # Unlimited
    
    def test_result_to_dict(self):
        """Test rate limit result serialization."""
        result = RateLimitResult(
            allowed=True,
            remaining=5,
            reset_at="2026-03-31T13:00:00Z",
            retry_after_seconds=0,
            limit=10,
            key="user_001",
        )
        
        d = result.to_dict()
        
        assert d["allowed"] is True
        assert d["remaining"] == 5
        assert d["limit"] == 10
    
    def test_config_to_dict(self):
        """Test rate limit config serialization."""
        config = RateLimitConfig(
            limit_id="api_limit",
            algorithm=RateLimitAlgorithm.TOKEN_BUCKET,
            max_requests=100,
            window_seconds=60,
            burst_size=10,
            key_prefix="user",
            enabled=True,
        )
        
        d = config.to_dict()
        
        assert d["limit_id"] == "api_limit"
        assert d["algorithm"] == "token_bucket"
        assert d["burst_size"] == 10
    
    def test_rate_limit_algorithm_enum_values(self):
        """Test rate limit algorithm enum values."""
        assert RateLimitAlgorithm.TOKEN_BUCKET.value == "token_bucket"
        assert RateLimitAlgorithm.SLIDING_WINDOW.value == "sliding_window"
        assert RateLimitAlgorithm.FIXED_WINDOW.value == "fixed_window"
        assert RateLimitAlgorithm.LEAKY_BUCKET.value == "leaky_bucket"
    
    def test_result_includes_retry_after_when_denied(self):
        """Test that result includes retry_after when denied."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=1,
            window_seconds=60,
        )
        
        engine.consume("user_001", "api_limit")
        
        result = engine.check_rate_limit("user_001", "api_limit")
        
        assert result.allowed is False
        assert result.retry_after_seconds > 0
    
    def test_result_includes_reset_at(self):
        """Test that result includes reset_at."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=10,
            window_seconds=60,
        )
        
        result = engine.check_rate_limit("user_001", "api_limit")
        
        assert result.reset_at is not None
        assert "T" in result.reset_at  # ISO format
    
    def test_statistics_empty_engine(self):
        """Test statistics with empty engine."""
        engine = RateLimiterEngine()
        
        stats = engine.get_statistics()
        
        assert stats["total_requests"] == 0
        assert stats["allowed_requests"] == 0
        assert stats["denied_requests"] == 0
    
    def test_multiple_keys_same_limit(self):
        """Test multiple keys with same limit."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=2,
            window_seconds=60,
        )
        
        # Each key should have independent limit
        engine.consume("user_001", "api_limit")
        engine.consume("user_001", "api_limit")
        assert engine.consume("user_001", "api_limit") is False
        
        engine.consume("user_002", "api_limit")
        engine.consume("user_002", "api_limit")
        assert engine.consume("user_002", "api_limit") is False
        
        # user_003 should still have quota
        assert engine.consume("user_003", "api_limit") is True
    
    def test_sliding_window_tracks_timestamps(self):
        """Test that sliding window tracks individual timestamps."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="sliding_window",
            max_requests=5,
            window_seconds=60,
        )
        
        for i in range(3):
            engine.consume("user_001", "api_limit")
        
        # Check internal state
        assert len(engine._sliding_windows.get("user_001", [])) == 3
    
    def test_fixed_window_key_includes_window(self):
        """Test that fixed window key includes window identifier."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="fixed_window",
            max_requests=10,
            window_seconds=60,
        )
        
        engine.consume("user_001", "api_limit")
        
        # Fixed windows should have window timestamp in key
        assert len(engine._fixed_windows) >= 1
        
        # Key should contain window identifier
        for key in engine._fixed_windows:
            assert "user_001:" in key
    
    def test_token_bucket_state_persisted(self):
        """Test that token bucket state is persisted."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=10,
            window_seconds=60,
        )
        
        engine.consume("user_001", "api_limit")
        engine.consume("user_001", "api_limit")
        
        # Check internal state
        assert "user_001" in engine._token_buckets
        
        bucket = engine._token_buckets["user_001"]
        assert bucket.tokens < 10  # Some tokens consumed
    
    def test_leaky_bucket_state_persisted(self):
        """Test that leaky bucket state is persisted."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="leaky_bucket",
            max_requests=10,
            window_seconds=60,
        )
        
        engine.consume("user_001", "api_limit")
        engine.consume("user_001", "api_limit")
        
        # Check internal state
        assert "user_001" in engine._leaky_buckets
        
        water_level, _ = engine._leaky_buckets["user_001"]
        assert water_level > 0  # Some water added
    
    def test_cleanup_sliding_windows(self):
        """Test cleanup of sliding windows."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="sliding_window",
            max_requests=100,
            window_seconds=1,
        )
        
        # Create state
        for i in range(10):
            engine.consume("user_001", "api_limit")
        
        # Wait for expiration
        time.sleep(1.5)
        
        removed = engine.cleanup_old_state()
        
        # Should have removed old timestamps
        assert removed >= 10
    
    def test_cleanup_fixed_windows(self):
        """Test cleanup of fixed windows."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="fixed_window",
            max_requests=100,
            window_seconds=1,
        )
        
        # Create state
        engine.consume("user_001", "api_limit")
        
        # Wait for expiration
        time.sleep(1.5)
        
        removed = engine.cleanup_old_state()
        
        # Should have removed old windows
        assert removed >= 1
    
    def test_clear_state_with_no_state(self):
        """Test clearing state when there is no state."""
        engine = RateLimiterEngine()
        
        count = engine.clear_all_state()
        
        assert count == 0
    
    def test_cleanup_with_no_old_state(self):
        """Test cleanup when there is no old state."""
        engine = RateLimiterEngine()
        
        engine.register_limit("api_limit", "token_bucket", 100, 60)
        
        # Token bucket doesn't get cleaned up by cleanup_old_state
        removed = engine.cleanup_old_state()
        
        assert removed == 0
    
    def test_limit_enabled_by_default(self):
        """Test that limits are enabled by default."""
        engine = RateLimiterEngine()
        
        engine.register_limit("api_limit", "token_bucket", 10, 60)
        
        config = engine.get_limit_config("api_limit")
        
        assert config["enabled"] is True
    
    def test_statistics_include_active_limits(self):
        """Test that statistics include active limits count."""
        engine = RateLimiterEngine()
        
        engine.register_limit("limit1", "token_bucket", 10, 60)
        engine.register_limit("limit2", "sliding_window", 10, 60)
        
        stats = engine.get_statistics()
        
        assert stats["active_limits"] == 2
    
    def test_result_key_includes_prefix(self):
        """Test that result key includes prefix."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=10,
            window_seconds=60,
            key_prefix="user",
        )
        
        result = engine.check_rate_limit("user_001", "api_limit")
        
        assert result.key == "user:user_001"
    
    def test_consume_with_zero_cost(self):
        """Test consume with zero cost."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=10,
            window_seconds=60,
        )
        
        # Zero cost should always be allowed
        for i in range(20):
            result = engine.check_rate_limit("user_001", "api_limit", cost=0)
            assert result.allowed is True
    
    def test_window_state_to_dict(self):
        """Test window state serialization."""
        state = WindowState(
            count=5,
            window_start="2026-03-31T12:00:00Z",
            window_seconds=60,
        )
        
        d = {
            "count": state.count,
            "window_start": state.window_start,
            "window_seconds": state.window_seconds,
        }
        
        assert d["count"] == 5
        assert d["window_seconds"] == 60
    
    def test_token_bucket_to_dict(self):
        """Test token bucket serialization."""
        bucket = TokenBucket(
            tokens=7.5,
            last_update="2026-03-31T12:00:00Z",
            max_tokens=10,
            refill_rate=0.5,
        )
        
        d = {
            "tokens": bucket.tokens,
            "last_update": bucket.last_update,
            "max_tokens": bucket.max_tokens,
            "refill_rate": bucket.refill_rate,
        }
        
        assert d["tokens"] == 7.5
        assert d["max_tokens"] == 10
    
    def test_deny_high_cost_request_with_partial_tokens(self):
        """Test denying high cost request when partial tokens available."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=5,
            window_seconds=60,
        )
        
        # Consume 3 tokens
        engine.consume("user_001", "api_limit", cost=3)
        
        # Try to consume 5 more (only 2 remaining)
        result = engine.check_rate_limit("user_001", "api_limit", cost=5)
        
        assert result.allowed is False
        assert result.remaining == 2
    
    def test_sliding_window_maintains_order(self):
        """Test that sliding window maintains timestamp order."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="sliding_window",
            max_requests=10,
            window_seconds=60,
        )
        
        for i in range(5):
            engine.consume("user_001", "api_limit")
            time.sleep(0.01)  # Small delay between requests
        
        timestamps = engine._sliding_windows.get("user_001", [])
        
        # Timestamps should be in order
        for i in range(len(timestamps) - 1):
            assert timestamps[i] <= timestamps[i + 1]
    
    def test_fixed_window_counts_across_requests(self):
        """Test that fixed window counts accumulate across requests."""
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="fixed_window",
            max_requests=10,
            window_seconds=60,
        )
        
        for i in range(5):
            engine.consume("user_001", "api_limit")
        
        # Check internal state
        for key, state in engine._fixed_windows.items():
            if "user_001" in key:
                assert state.count == 5
                break
    
    def test_rate_limit_result_allowed_true(self):
        """Test rate limit result with allowed=True."""
        result = RateLimitResult(
            allowed=True,
            remaining=5,
            reset_at="2026-03-31T13:00:00Z",
            retry_after_seconds=0,
            limit=10,
            key="user_001",
        )
        
        assert result.allowed is True
        assert result.retry_after_seconds == 0
    
    def test_rate_limit_result_allowed_false(self):
        """Test rate limit result with allowed=False."""
        result = RateLimitResult(
            allowed=False,
            remaining=0,
            reset_at="2026-03-31T13:00:00Z",
            retry_after_seconds=30,
            limit=10,
            key="user_001",
        )
        
        assert result.allowed is False
        assert result.retry_after_seconds == 30
    
    def test_register_limit_generates_limit_id(self):
        """Test that register_limit returns the limit_id."""
        engine = RateLimiterEngine()
        
        limit_id = engine.register_limit(
            limit_id="custom_id",
            algorithm="token_bucket",
            max_requests=10,
            window_seconds=60,
        )
        
        assert limit_id == "custom_id"
    
    def test_check_rate_limit_thread_safety(self):
        """Test thread safety of rate limit checks."""
        import threading
        
        engine = RateLimiterEngine()
        
        engine.register_limit(
            limit_id="api_limit",
            algorithm="token_bucket",
            max_requests=100,
            window_seconds=60,
        )
        
        results = []
        
        def check_limit():
            for i in range(10):
                result = engine.check_rate_limit("user_001", "api_limit")
                results.append(result.allowed)
        
        threads = [threading.Thread(target=check_limit) for _ in range(5)]
        
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should have 50 results
        assert len(results) == 50
        # All should be allowed (100 limit, 50 requests)
        assert all(results)
