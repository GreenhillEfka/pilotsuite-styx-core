"""
Rate Limiting Tests

Tests for the Token Bucket rate limiting implementation.

Covers:
- Token bucket algorithm correctness
- Per-API-Key limits
- Default limits (100 req/min, burst 20)
- Response headers (X-RateLimit-*)
- 429 responses with Retry-After
"""

import pytest
import time
from unittest.mock import Mock, patch

from copilot_core.models.rate_limit import (
    RateLimitConfig,
    RateLimitAlgorithm,
    TokenBucket,
    RateLimitHeaders,
    RateLimitStatus,
    DEFAULT_RATE_LIMIT_CONFIG,
)
from copilot_core.api.middleware.rate_limit import (
    RateLimitStore,
    get_rate_limit_store,
    extract_client_id,
    rate_limit_exceeded_response,
    add_rate_limit_headers,
    rate_limit_middleware,
    init_rate_limiting,
    with_rate_limit,
)


class TestRateLimitConfig:
    """Test RateLimitConfig dataclass."""
    
    def test_default_config(self):
        """Test default configuration values."""
        config = DEFAULT_RATE_LIMIT_CONFIG
        
        assert config.requests_per_minute == 100
        assert config.burst_size == 20
        assert config.algorithm == RateLimitAlgorithm.TOKEN_BUCKET
        assert config.enabled is True
    
    def test_custom_config(self):
        """Test custom configuration."""
        config = RateLimitConfig(
            requests_per_minute=50,
            burst_size=10,
            enabled=False,
        )
        
        assert config.requests_per_minute == 50
        assert config.burst_size == 10
        assert config.enabled is False
    
    def test_refill_rate_calculation(self):
        """Test refill rate property."""
        config = RateLimitConfig(requests_per_minute=60)
        assert config.refill_rate == 1.0  # 1 token per second
        
        config = RateLimitConfig(requests_per_minute=120)
        assert config.refill_rate == 2.0  # 2 tokens per second
        
        config = RateLimitConfig(requests_per_minute=30)
        assert config.refill_rate == 0.5  # 0.5 tokens per second
    
    def test_to_dict_serialization(self):
        """Test config serialization to dict."""
        config = RateLimitConfig(
            requests_per_minute=100,
            burst_size=20,
            api_key="test-key",
        )
        
        data = config.to_dict()
        
        assert data["requests_per_minute"] == 100
        assert data["burst_size"] == 20
        assert data["algorithm"] == "token_bucket"
        assert data["enabled"] is True
        assert data["api_key"] == "test-key"
        assert "refill_rate" in data
    
    def test_from_dict_deserialization(self):
        """Test config deserialization from dict."""
        data = {
            "requests_per_minute": 50,
            "burst_size": 10,
            "algorithm": "token_bucket",
            "enabled": False,
            "api_key": "custom-key",
        }
        
        config = RateLimitConfig.from_dict(data)
        
        assert config.requests_per_minute == 50
        assert config.burst_size == 10
        assert config.algorithm == RateLimitAlgorithm.TOKEN_BUCKET
        assert config.enabled is False
        assert config.api_key == "custom-key"


class TestTokenBucket:
    """Test TokenBucket implementation."""
    
    def test_initial_bucket_state(self):
        """Test bucket starts full."""
        config = RateLimitConfig(requests_per_minute=60, burst_size=10)
        bucket = TokenBucket.from_config(config)
        
        assert bucket.capacity == 10
        assert bucket.tokens == 10.0
        assert bucket.refill_rate == 1.0
    
    def test_consume_tokens_success(self):
        """Test successful token consumption."""
        config = RateLimitConfig(requests_per_minute=60, burst_size=10)
        bucket = TokenBucket.from_config(config)
        
        # Consume 5 tokens
        allowed, remaining = bucket.consume(5)
        
        assert allowed is True
        assert remaining == 5.0
    
    def test_consume_tokens_failure(self):
        """Test token consumption failure when empty."""
        config = RateLimitConfig(requests_per_minute=60, burst_size=5)
        bucket = TokenBucket.from_config(config)
        
        # Consume all tokens
        bucket.consume(5)
        
        # Try to consume more (allow small timing variance for refill)
        allowed, remaining = bucket.consume(1)
        
        assert allowed is False
        assert remaining < 1.0  # Less than 1 token remaining
    
    def test_token_refill(self):
        """Test token refill over time."""
        config = RateLimitConfig(requests_per_minute=60, burst_size=10)
        bucket = TokenBucket.from_config(config)
        
        # Consume all tokens
        bucket.consume(10)
        assert bucket.tokens == 0.0
        
        # Wait 5 seconds (should add 5 tokens at 1/sec)
        bucket.last_refill = time.time() - 5.0
        allowed, remaining = bucket.consume(1)
        
        assert allowed is True
        assert 4.0 <= remaining <= 5.0  # Allow small timing variance
    
    def test_bucket_capacity_limit(self):
        """Test bucket doesn't exceed capacity."""
        config = RateLimitConfig(requests_per_minute=60, burst_size=10)
        bucket = TokenBucket.from_config(config)
        
        # Set last_refill far in the past
        bucket.last_refill = time.time() - 100.0
        
        # Consume should refill but cap at capacity
        allowed, remaining = bucket.consume(1)
        
        assert allowed is True
        assert remaining == 9.0  # Capacity - 1
    
    def test_get_wait_time(self):
        """Test wait time calculation."""
        config = RateLimitConfig(requests_per_minute=60, burst_size=10)
        bucket = TokenBucket.from_config(config)
        
        # Full bucket
        wait = bucket.get_wait_time(1)
        assert wait == 0.0
        
        # Empty bucket
        bucket.consume(10)
        wait = bucket.get_wait_time(1)
        assert 0.5 <= wait <= 1.5  # Should be ~1 second at 1 token/sec
    
    def test_bucket_to_dict(self):
        """Test bucket serialization."""
        config = RateLimitConfig(requests_per_minute=60, burst_size=10)
        bucket = TokenBucket.from_config(config)
        
        data = bucket.to_dict()
        
        assert data["capacity"] == 10
        assert data["tokens"] == 10.0
        assert data["refill_rate"] == 1.0
        assert "last_refill" in data


class TestRateLimitHeaders:
    """Test RateLimitHeaders."""
    
    def test_headers_to_dict(self):
        """Test header conversion to dict."""
        headers = RateLimitHeaders(
            limit=100,
            remaining=50,
            reset=1234567890,
            retry_after=30,
        )
        
        data = headers.to_dict()
        
        assert data["X-RateLimit-Limit"] == "100"
        assert data["X-RateLimit-Remaining"] == "50"
        assert data["X-RateLimit-Reset"] == "1234567890"
        assert data["Retry-After"] == "30"
    
    def test_headers_without_retry(self):
        """Test headers without Retry-After."""
        headers = RateLimitHeaders(
            limit=100,
            remaining=50,
            reset=1234567890,
        )
        
        data = headers.to_dict()
        
        assert "Retry-After" not in data
        assert data["X-RateLimit-Limit"] == "100"


class TestRateLimitStore:
    """Test RateLimitStore."""
    
    def test_get_bucket_creates_new(self):
        """Test bucket creation for new client."""
        store = RateLimitStore()
        config = RateLimitConfig(requests_per_minute=60, burst_size=10)
        
        bucket = store.get_bucket("client1", config)
        
        assert bucket.capacity == 10
        assert bucket.tokens == 10.0
    
    def test_get_bucket_returns_existing(self):
        """Test same bucket returned for existing client."""
        store = RateLimitStore()
        config = RateLimitConfig(requests_per_minute=60, burst_size=10)
        
        bucket1 = store.get_bucket("client1", config)
        bucket2 = store.get_bucket("client1", config)
        
        assert bucket1 is bucket2
    
    def test_update_config_resets_bucket(self):
        """Test config update resets bucket."""
        store = RateLimitStore()
        config1 = RateLimitConfig(requests_per_minute=60, burst_size=10)
        config2 = RateLimitConfig(requests_per_minute=120, burst_size=20)
        
        bucket1 = store.get_bucket("client1", config1)
        bucket1.consume(5)  # Use some tokens
        
        store.update_config("client1", config2)
        bucket2 = store.get_bucket("client1", config2)
        
        assert bucket2 is not bucket1
        assert bucket2.capacity == 20
        assert bucket2.tokens == 20.0  # Reset to full
    
    def test_remove_client(self):
        """Test client removal."""
        store = RateLimitStore()
        config = RateLimitConfig(requests_per_minute=60, burst_size=10)
        
        store.get_bucket("client1", config)
        store.remove_client("client1")
        
        assert store.get_config("client1") is None
    
    def test_get_all_status(self):
        """Test getting status for all clients."""
        store = RateLimitStore()
        config = RateLimitConfig(requests_per_minute=60, burst_size=10)
        
        store.get_bucket("client1", config)
        store.get_bucket("client2", config)
        
        status = store.get_all_status()
        
        assert len(status) == 2
        assert "client1" in status
        assert "client2" in status
    
    def test_cleanup_stale(self):
        """Test stale client cleanup."""
        store = RateLimitStore()
        config = RateLimitConfig(requests_per_minute=60, burst_size=10)
        
        # Add client
        store.get_bucket("client1", config)
        
        # Manually set last_refill to past
        bucket = store.get_bucket("client1", config)
        bucket.last_refill = time.time() - 7200  # 2 hours ago
        
        removed = store.cleanup_stale(max_age_seconds=3600)
        
        assert removed == 1
        assert store.get_config("client1") is None


class TestRateLimitMiddleware:
    """Test rate limiting middleware."""
    
    def test_extract_client_id_from_api_key(self):
        """Test client ID extraction from API key header."""
        from flask import Flask
        
        app = Flask(__name__)
        
        @app.route("/test")
        def test_route():
            from copilot_core.api.middleware.rate_limit import extract_client_id
            client_id = extract_client_id()
            return client_id
        
        with app.test_client() as client:
            response = client.get("/test", headers={"X-API-Key": "test-key-123"})
            assert response.data.decode() == "apikey:test-key-123"
    
    def test_extract_client_id_from_ip(self):
        """Test client ID extraction from IP."""
        from flask import Flask
        
        app = Flask(__name__)
        
        @app.route("/test")
        def test_route():
            from copilot_core.api.middleware.rate_limit import extract_client_id
            return extract_client_id()
        
        with app.test_client() as client:
            response = client.get("/test")
            # Should be ip:127.0.0.1 for test client
            assert response.data.decode().startswith("ip:")
    
    def test_rate_limit_middleware_allows_valid_request(self):
        """Test middleware allows requests within limit."""
        from flask import Flask
        
        app = Flask(__name__)
        config = RateLimitConfig(requests_per_minute=60, burst_size=10)
        
        @app.route("/test")
        def test_route():
            return "OK"
        
        # Initialize rate limiting
        init_rate_limiting(app)
        
        with app.test_client() as client:
            response = client.get("/test", headers={"X-API-Key": "test-key"})
            # Should be allowed (200)
            assert response.status_code == 200
    
    def test_with_rate_limit_decorator(self):
        """Test rate limit decorator on endpoint."""
        config = RateLimitConfig(requests_per_minute=10, burst_size=5)
        
        @with_rate_limit(config)
        def test_endpoint():
            return "OK"
        
        assert hasattr(test_endpoint, 'rate_limit_config')
        assert test_endpoint.rate_limit_config == config


class TestIntegration:
    """Integration tests for rate limiting."""
    
    def test_burst_limit_enforcement(self):
        """Test burst limit is enforced."""
        config = RateLimitConfig(requests_per_minute=60, burst_size=5)
        bucket = TokenBucket.from_config(config)
        
        # Consume all burst tokens
        for i in range(5):
            allowed, _ = bucket.consume(1)
            assert allowed is True, f"Request {i+1} should be allowed"
        
        # Next request should be rejected (allow tiny refill variance)
        allowed, remaining = bucket.consume(1)
        assert allowed is False
        assert remaining < 1.0
    
    def test_sustained_rate_enforcement(self):
        """Test sustained rate limit over time."""
        config = RateLimitConfig(requests_per_minute=60, burst_size=10)
        bucket = TokenBucket.from_config(config)
        
        # Consume all tokens
        for _ in range(10):
            bucket.consume(1)
        
        # Wait 1 second (should add 1 token)
        bucket.last_refill = time.time() - 1.0
        
        # Should be able to make 1 request
        allowed, _ = bucket.consume(1)
        assert allowed is True
        
        # Next should fail
        allowed, _ = bucket.consume(1)
        assert allowed is False
    
    def test_headers_included_on_response(self):
        """Test rate limit headers are included."""
        config = RateLimitConfig(requests_per_minute=100, burst_size=20)
        bucket = TokenBucket.from_config(config)
        
        # Consume some tokens
        bucket.consume(5)
        
        # Create mock response
        mock_response = Mock()
        mock_response.headers = {}
        
        result = add_rate_limit_headers(mock_response, config, bucket, True)
        
        assert "X-RateLimit-Limit" in result.headers
        assert "X-RateLimit-Remaining" in result.headers
        assert "X-RateLimit-Reset" in result.headers
        
        # Check values
        assert int(result.headers["X-RateLimit-Limit"]) == 100
        assert int(result.headers["X-RateLimit-Remaining"]) >= 14  # 20 - 5 - small refill
        assert int(result.headers["X-RateLimit-Reset"]) > int(time.time())


class TestDefaultConfiguration:
    """Test default rate limit configuration matches spec."""
    
    def test_default_requests_per_minute(self):
        """Test default is 100 requests per minute."""
        assert DEFAULT_RATE_LIMIT_CONFIG.requests_per_minute == 100
    
    def test_default_burst_size(self):
        """Test default burst is 20."""
        assert DEFAULT_RATE_LIMIT_CONFIG.burst_size == 20
    
    def test_default_algorithm(self):
        """Test default algorithm is token bucket."""
        assert DEFAULT_RATE_LIMIT_CONFIG.algorithm == RateLimitAlgorithm.TOKEN_BUCKET
    
    def test_default_enabled(self):
        """Test rate limiting is enabled by default."""
        assert DEFAULT_RATE_LIMIT_CONFIG.enabled is True
