"""Tests for API Gateway & Rate Limiting — Slice 25."""
import pytest
from copilot_core.gateway.engine import (
    APIGatewayEngine,
    RateLimitStrategy,
    RequestStatus,
    create_api_gateway_engine,
)


class TestAPIGatewayEngine:
    """Test API gateway engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_api_gateway_engine()
        assert engine is not None
    
    def test_create_api_key(self):
        """Test API key creation."""
        engine = APIGatewayEngine()
        
        key_id, raw_key = engine.create_api_key(
            name="Test Key",
            owner="user_test",
        )
        
        assert key_id is not None
        assert key_id.startswith("key_")
        assert raw_key is not None
        assert len(raw_key) > 32  # token_urlsafe(32)
        assert key_id in engine._api_keys
    
    def test_create_api_key_with_custom_limits(self):
        """Test API key creation with custom limits."""
        engine = APIGatewayEngine()
        
        key_id, raw_key = engine.create_api_key(
            name="Limited Key",
            owner="user_test",
            rate_limit=50,
            quota_daily=1000,
        )
        
        api_key = engine._api_keys[key_id]
        assert api_key.rate_limit == 50
        assert api_key.quota_daily == 1000
    
    def test_create_api_key_with_expiry(self):
        """Test API key creation with expiry."""
        engine = APIGatewayEngine()
        
        key_id, raw_key = engine.create_api_key(
            name="Expiring Key",
            owner="user_test",
            expires_days=30,
        )
        
        api_key = engine._api_keys[key_id]
        assert api_key.expires_at is not None
    
    def test_validate_api_key_valid(self):
        """Test validating valid API key."""
        engine = APIGatewayEngine()
        
        key_id, raw_key = engine.create_api_key(
            name="Test Key",
            owner="user_test",
        )
        
        api_key = engine.validate_api_key(raw_key)
        
        assert api_key is not None
        assert api_key.key_id == key_id
    
    def test_validate_api_key_invalid(self):
        """Test validating invalid API key."""
        engine = APIGatewayEngine()
        
        api_key = engine.validate_api_key("invalid_key")
        
        assert api_key is None
    
    def test_validate_api_key_disabled(self):
        """Test validating disabled API key."""
        engine = APIGatewayEngine()
        
        key_id, raw_key = engine.create_api_key(
            name="Test Key",
            owner="user_test",
        )
        
        # Revoke key
        engine.revoke_api_key(key_id)
        
        api_key = engine.validate_api_key(raw_key)
        
        assert api_key is None
    
    def test_validate_api_key_expired(self):
        """Test validating expired API key."""
        engine = APIGatewayEngine()
        
        key_id, raw_key = engine.create_api_key(
            name="Test Key",
            owner="user_test",
            expires_days=-1,  # Already expired
        )
        
        api_key = engine.validate_api_key(raw_key)
        
        assert api_key is None
    
    def test_check_rate_limit_allowed(self):
        """Test rate limit check - allowed."""
        engine = APIGatewayEngine(default_rate_limit=10)
        
        status, state = engine.check_rate_limit("client_1")
        
        assert status == RequestStatus.ALLOWED
        assert state.requests_count == 1
    
    def test_check_rate_limit_exceeded(self):
        """Test rate limit check - exceeded."""
        engine = APIGatewayEngine(default_rate_limit=3)
        
        # Make requests up to limit
        for i in range(3):
            engine.check_rate_limit("client_1")
        
        # Next request should be rate limited
        status, state = engine.check_rate_limit("client_1")
        
        assert status == RequestStatus.RATE_LIMITED
    
    def test_check_rate_limit_with_api_key(self):
        """Test rate limit check with API key."""
        engine = APIGatewayEngine()
        
        key_id, raw_key = engine.create_api_key(
            name="Test Key",
            owner="user_test",
            rate_limit=5,
        )
        
        api_key = engine.validate_api_key(raw_key)
        
        # Make requests
        for i in range(5):
            status, state = engine.check_rate_limit("client_1", api_key)
            assert status == RequestStatus.ALLOWED
        
        # Next should be limited
        status, state = engine.check_rate_limit("client_1", api_key)
        assert status == RequestStatus.RATE_LIMITED
    
    def test_check_quota_exceeded(self):
        """Test quota exceeded check."""
        engine = APIGatewayEngine()
        
        key_id, raw_key = engine.create_api_key(
            name="Test Key",
            owner="user_test",
            quota_daily=5,
        )
        
        api_key = engine.validate_api_key(raw_key)
        
        # Use up quota
        for i in range(5):
            engine.check_rate_limit("client_1", api_key)
        
        # Next should exceed quota
        status, state = engine.check_rate_limit("client_1", api_key)
        
        assert status == RequestStatus.QUOTA_EXCEEDED
    
    def test_process_request_allowed(self):
        """Test processing allowed request."""
        engine = APIGatewayEngine()
        
        key_id, raw_key = engine.create_api_key(
            name="Test Key",
            owner="user_test",
        )
        
        result = engine.process_request(
            client_id="client_1",
            endpoint="/api/test",
            method="GET",
            raw_key=raw_key,
        )
        
        assert result["status"] == "allowed"
        assert "rate_limit_remaining" in result
    
    def test_process_request_invalid_key(self):
        """Test processing request with invalid key."""
        engine = APIGatewayEngine()
        
        result = engine.process_request(
            client_id="client_1",
            endpoint="/api/test",
            method="GET",
            raw_key="invalid_key",
        )
        
        assert result["status"] == "blocked"
        assert "Invalid API key" in result["error"]
    
    def test_process_request_rate_limited(self):
        """Test processing rate limited request."""
        engine = APIGatewayEngine(default_rate_limit=2)
        
        # Use up rate limit
        engine.process_request("client_1", "/api/test", "GET")
        engine.process_request("client_1", "/api/test", "GET")
        
        # Next should be rate limited
        result = engine.process_request("client_1", "/api/test", "GET")
        
        assert result["status"] == "rate_limited"
        assert "retry_after" in result
    
    def test_log_request(self):
        """Test request logging."""
        engine = APIGatewayEngine()
        
        log_id = engine.log_request(
            client_id="client_1",
            endpoint="/api/test",
            method="GET",
            status=RequestStatus.ALLOWED,
            response_time_ms=50,
            rate_limit_remaining=99,
        )
        
        assert log_id is not None
        assert log_id.startswith("log_")
        assert len(engine._request_logs) == 1
    
    def test_get_request_logs(self):
        """Test getting request logs."""
        engine = APIGatewayEngine()
        
        # Create some logs
        for i in range(5):
            engine.log_request(
                client_id="client_1",
                endpoint="/api/test",
                method="GET",
                status=RequestStatus.ALLOWED,
                response_time_ms=50,
            )
        
        logs = engine.get_request_logs(limit=10)
        
        assert len(logs) == 5
    
    def test_get_request_logs_filtered_by_client(self):
        """Test getting logs filtered by client."""
        engine = APIGatewayEngine()
        
        engine.log_request("client_a", "/api/test", "GET", RequestStatus.ALLOWED, 50)
        engine.log_request("client_b", "/api/test", "GET", RequestStatus.ALLOWED, 50)
        engine.log_request("client_a", "/api/test", "GET", RequestStatus.ALLOWED, 50)
        
        logs_a = engine.get_request_logs(client_id="client_a")
        logs_b = engine.get_request_logs(client_id="client_b")
        
        assert len(logs_a) == 2
        assert len(logs_b) == 1
    
    def test_get_request_logs_filtered_by_status(self):
        """Test getting logs filtered by status."""
        engine = APIGatewayEngine()
        
        engine.log_request("client_1", "/api/test", "GET", RequestStatus.ALLOWED, 50)
        engine.log_request("client_1", "/api/test", "GET", RequestStatus.RATE_LIMITED, 0)
        engine.log_request("client_1", "/api/test", "GET", RequestStatus.ALLOWED, 50)
        
        logs_limited = engine.get_request_logs(status=RequestStatus.RATE_LIMITED)
        
        assert len(logs_limited) == 1
    
    def test_get_api_keys(self):
        """Test getting API keys."""
        engine = APIGatewayEngine()
        
        engine.create_api_key("Key 1", "owner_a")
        engine.create_api_key("Key 2", "owner_a")
        engine.create_api_key("Key 3", "owner_b")
        
        all_keys = engine.get_api_keys()
        keys_a = engine.get_api_keys(owner="owner_a")
        
        assert len(all_keys) == 3
        assert len(keys_a) == 2
    
    def test_revoke_api_key(self):
        """Test revoking API key."""
        engine = APIGatewayEngine()
        
        key_id, raw_key = engine.create_api_key(
            name="Test Key",
            owner="user_test",
        )
        
        result = engine.revoke_api_key(key_id)
        
        assert result is True
        assert engine._api_keys[key_id].enabled is False
    
    def test_revoke_unknown_api_key(self):
        """Test revoking unknown API key."""
        engine = APIGatewayEngine()
        
        result = engine.revoke_api_key("unknown_key")
        
        assert result is False
    
    def test_reset_quota(self):
        """Test resetting quota."""
        engine = APIGatewayEngine()
        
        key_id, raw_key = engine.create_api_key(
            name="Test Key",
            owner="user_test",
            quota_daily=100,
        )
        
        api_key = engine.validate_api_key(raw_key)
        
        # Use some quota
        for i in range(50):
            engine.check_rate_limit("client_1", api_key)
        
        assert engine._api_keys[key_id].quota_used_today == 50
        
        # Reset
        result = engine.reset_quota(key_id)
        
        assert result is True
        assert engine._api_keys[key_id].quota_used_today == 0
    
    def test_get_rate_limit_status(self):
        """Test getting rate limit status."""
        engine = APIGatewayEngine()
        
        engine.check_rate_limit("client_1")
        engine.check_rate_limit("client_1")
        
        status = engine.get_rate_limit_status("client_1")
        
        assert status is not None
        assert status["requests_count"] == 2
    
    def test_get_gateway_summary(self):
        """Test gateway summary."""
        engine = APIGatewayEngine()
        
        # Create keys
        engine.create_api_key("Key 1", "owner_a")
        engine.create_api_key("Key 2", "owner_b")
        
        # Make some requests
        engine.process_request("client_1", "/api/test", "GET")
        engine.process_request("client_1", "/api/test", "GET")
        
        summary = engine.get_gateway_summary()
        
        assert summary["total_api_keys"] == 2
        assert summary["active_api_keys"] == 2
        assert summary["total_requests"] >= 2
    
    def test_reset_daily_quotas(self):
        """Test resetting all daily quotas."""
        engine = APIGatewayEngine()
        
        # Create keys and use quota
        for i in range(3):
            key_id, raw_key = engine.create_api_key(f"Key {i}", "owner")
            api_key = engine.validate_api_key(raw_key)
            for j in range(10):
                engine.check_rate_limit(f"client_{i}", api_key)
        
        # Reset all
        count = engine.reset_daily_quotas()
        
        assert count == 3
        
        # All quotas should be reset
        for api_key in engine._api_keys.values():
            assert api_key.quota_used_today == 0
    
    def test_request_logs_sorted_newest_first(self):
        """Test that logs are sorted newest first."""
        engine = APIGatewayEngine()
        
        for i in range(5):
            engine.log_request("client_1", "/api/test", "GET", RequestStatus.ALLOWED, 50)
        
        logs = engine.get_request_logs(limit=10)
        
        # Verify sorted by timestamp (newest first)
        for i in range(len(logs) - 1):
            assert logs[i]["timestamp"] >= logs[i + 1]["timestamp"]
    
    def test_logs_trimmed_to_max(self):
        """Test that logs are trimmed to max size."""
        engine = APIGatewayEngine()
        
        # Create more than max logs
        for i in range(10050):
            engine.log_request("client_1", "/api/test", "GET", RequestStatus.ALLOWED, 50)
        
        assert len(engine._request_logs) <= 10000
    
    def test_api_key_to_dict(self):
        """Test API key serialization."""
        from copilot_core.gateway.engine import APIKey
        
        key = APIKey(
            key_id="key_test",
            key_hash="abc123",
            name="Test Key",
            owner="user_test",
            rate_limit=100,
            quota_daily=10000,
        )
        
        d = key.to_dict()
        
        assert d["key_id"] == "key_test"
        assert d["name"] == "Test Key"
        assert d["owner"] == "user_test"
        # Note: key_hash is NOT included in to_dict for security
    
    def test_rate_limit_state_to_dict(self):
        """Test rate limit state serialization."""
        from copilot_core.gateway.engine import RateLimitState
        
        state = RateLimitState(
            client_id="client_test",
            window_start="2026-03-31T12:00:00Z",
            requests_count=50,
            requests_allowed=48,
            requests_denied=2,
            reset_at="2026-03-31T12:01:00Z",
        )
        
        d = state.to_dict()
        
        assert d["client_id"] == "client_test"
        assert d["requests_count"] == 50
        assert d["requests_allowed"] == 48
        assert d["requests_denied"] == 2
    
    def test_request_log_to_dict(self):
        """Test request log serialization."""
        from copilot_core.gateway.engine import RequestLog
        
        log = RequestLog(
            log_id="log_test",
            timestamp="2026-03-31T12:00:00Z",
            client_id="client_test",
            api_key_id="key_test",
            endpoint="/api/test",
            method="GET",
            status=RequestStatus.ALLOWED,
            response_time_ms=50,
            rate_limit_remaining=99,
        )
        
        d = log.to_dict()
        
        assert d["log_id"] == "log_test"
        assert d["status"] == "allowed"
        assert d["response_time_ms"] == 50
    
    def test_add_middleware(self):
        """Test adding middleware."""
        engine = APIGatewayEngine()
        
        def test_middleware(request):
            pass
        
        engine.add_middleware(test_middleware)
        
        assert len(engine._middleware) == 1
    
    def test_different_rate_limit_strategies(self):
        """Test different rate limit strategies."""
        engine_fixed = APIGatewayEngine(strategy=RateLimitStrategy.FIXED_WINDOW)
        engine_sliding = APIGatewayEngine(strategy=RateLimitStrategy.SLIDING_WINDOW)
        engine_token = APIGatewayEngine(strategy=RateLimitStrategy.TOKEN_BUCKET)
        
        assert engine_fixed._strategy == RateLimitStrategy.FIXED_WINDOW
        assert engine_sliding._strategy == RateLimitStrategy.SLIDING_WINDOW
        assert engine_token._strategy == RateLimitStrategy.TOKEN_BUCKET
