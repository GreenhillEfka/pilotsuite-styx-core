"""
Tests for the Error Handling Framework.
"""

import asyncio
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import time

from .error_handler import (
    ErrorHandler,
    ErrorClassification,
    CircuitBreaker,
    CircuitBreakerState,
    CircuitBreakerOpenError,
    RetryConfig,
    CircuitBreakerConfig,
    FallbackStrategy,
    ErrorContext,
    with_error_handler,
)


class TestErrorClassification:
    """Test error classification logic."""
    
    def test_classify_network_timeout(self):
        handler = ErrorHandler()
        exc = TimeoutError("Connection timed out")
        assert handler.classify_error(exc) == ErrorClassification.NETWORK_TIMEOUT
    
    def test_classify_rate_limit(self):
        handler = ErrorHandler()
        exc = Exception("Rate limit exceeded: 429")
        assert handler.classify_error(exc) == ErrorClassification.RATE_LIMIT
    
    def test_classify_connection_lost(self):
        handler = ErrorHandler()
        exc = ConnectionError("Connection lost to server")
        assert handler.classify_error(exc) == ErrorClassification.CONNECTION_LOST
    
    def test_classify_auth_failed(self):
        handler = ErrorHandler()
        exc = Exception("Authentication failed: 401")
        assert handler.classify_error(exc) == ErrorClassification.AUTHENTICATION_FAILED
    
    def test_classify_permission_denied(self):
        handler = ErrorHandler()
        exc = Exception("Permission denied: 403")
        assert handler.classify_error(exc) == ErrorClassification.PERMISSION_DENIED
    
    def test_classify_validation_error(self):
        handler = ErrorHandler()
        exc = ValueError("Validation failed: invalid input")
        assert handler.classify_error(exc) == ErrorClassification.VALIDATION_ERROR
    
    def test_classify_critical_default(self):
        handler = ErrorHandler()
        exc = RuntimeError("Unknown error occurred")
        assert handler.classify_error(exc) == ErrorClassification.CRITICAL_FAILURE


class TestRetryLogic:
    """Test retry with exponential backoff."""
    
    @pytest.mark.asyncio
    async def test_retry_success_on_first_try(self):
        handler = ErrorHandler(retry_config=RetryConfig(max_retries=3))
        
        call_count = 0
        async def func():
            nonlocal call_count
            call_count += 1
            return "success"
        
        result = await handler.execute_with_retry(func)
        assert result == "success"
        assert call_count == 1
    
    @pytest.mark.asyncio
    async def test_retry_on_failure(self):
        handler = ErrorHandler(retry_config=RetryConfig(max_retries=3, base_delay=0.01))
        
        call_count = 0
        async def func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise TimeoutError("Temporary failure")
            return "success"
        
        result = await handler.execute_with_retry(func)
        assert result == "success"
        assert call_count == 3
    
    @pytest.mark.asyncio
    async def test_no_retry_on_fatal_error(self):
        handler = ErrorHandler(retry_config=RetryConfig(max_retries=3))
        
        call_count = 0
        async def func():
            nonlocal call_count
            call_count += 1
            raise Exception("Authentication failed: 401")
        
        with pytest.raises(Exception):
            await handler.execute_with_retry(func)
        
        assert call_count == 1  # Should not retry fatal errors
    
    @pytest.mark.asyncio
    async def test_max_retries_exceeded(self):
        handler = ErrorHandler(retry_config=RetryConfig(max_retries=2, base_delay=0.01))
        
        call_count = 0
        async def func():
            nonlocal call_count
            call_count += 1
            raise TimeoutError("Always fails")
        
        with pytest.raises(TimeoutError):
            await handler.execute_with_retry(func)
        
        assert call_count == 3  # Initial + 2 retries


class TestCircuitBreaker:
    """Test circuit breaker pattern."""
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_closed_normal_operation(self):
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3))
        
        async def func():
            return "success"
        
        result = await cb.call(func)
        assert result == "success"
        assert cb.state == CircuitBreakerState.CLOSED
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_opens_after_failures(self):
        cb = CircuitBreaker(CircuitBreakerConfig(failure_threshold=3, recovery_timeout=0.1))
        
        async def failing_func():
            raise Exception("Service down")
        
        # Fail 3 times to open circuit
        for _ in range(3):
            with pytest.raises(Exception):
                await cb.call(failing_func)
        
        assert cb.state == CircuitBreakerState.OPEN
        
        # Should reject immediately
        with pytest.raises(CircuitBreakerOpenError):
            await cb.call(failing_func)
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_half_open_recovery(self):
        cb = CircuitBreaker(CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=0.1,
            half_open_max_calls=1
        ))
        
        async def failing_func():
            raise Exception("Service down")
        
        async def success_func():
            return "recovered"
        
        # Open circuit
        for _ in range(2):
            with pytest.raises(Exception):
                await cb.call(failing_func)
        
        assert cb.state == CircuitBreakerState.OPEN
        
        # Wait for recovery timeout
        await asyncio.sleep(0.15)
        
        # Should transition to half-open and allow one call
        result = await cb.call(success_func)
        assert result == "recovered"
        assert cb.state == CircuitBreakerState.CLOSED


class TestFallbackStrategy:
    """Test fallback strategy pattern."""
    
    @pytest.mark.asyncio
    async def test_fallback_primary_success(self):
        strategy = FallbackStrategy()
        
        async def primary():
            return "primary_result"
        
        result = await strategy.execute(primary)
        assert result == "primary_result"
    
    @pytest.mark.asyncio
    async def test_fallback_on_primary_failure(self):
        strategy = FallbackStrategy()
        
        async def primary():
            raise Exception("Primary failed")
        
        async def fallback():
            return "fallback_result"
        
        strategy.add_fallback(fallback, priority=1)
        
        result = await strategy.execute(primary)
        assert result == "fallback_result"
    
    @pytest.mark.asyncio
    async def test_fallback_priority_order(self):
        strategy = FallbackStrategy()
        
        async def primary():
            raise Exception("Primary failed")
        
        async def fallback1():
            raise Exception("Fallback 1 failed")
        
        async def fallback2():
            return "fallback2_result"
        
        strategy.add_fallback(fallback1, priority=1)
        strategy.add_fallback(fallback2, priority=2)
        
        result = await strategy.execute(primary)
        assert result == "fallback2_result"
    
    @pytest.mark.asyncio
    async def test_fallback_all_fail(self):
        strategy = FallbackStrategy()
        
        async def primary():
            raise Exception("Primary failed")
        
        async def fallback():
            raise Exception("Fallback also failed")
        
        strategy.add_fallback(fallback, priority=1)
        
        with pytest.raises(Exception):
            await strategy.execute(primary)


class TestErrorHandler:
    """Test central error handler."""
    
    def test_error_recording(self):
        handler = ErrorHandler(component="test_component")
        
        exc = ValueError("Test error")
        context = handler.record_error(exc, {"key": "value"})
        
        assert context.error_type == "ValueError"
        assert context.component == "test_component"
        assert context.metadata == {"key": "value"}
        assert len(handler.error_history) == 1
    
    def test_error_summary(self):
        handler = ErrorHandler(component="test")
        
        # Record multiple errors
        handler.record_error(TimeoutError("timeout 1"))
        handler.record_error(TimeoutError("timeout 2"))
        handler.record_error(Exception("Auth failed: 401"))
        
        summary = handler.get_error_summary()
        
        assert summary["total"] == 3
        assert "network_timeout" in summary["by_classification"]
        assert summary["by_classification"]["network_timeout"] == 2
    
    def test_custom_handler_registration(self):
        handler = ErrorHandler()
        
        custom_called = False
        
        def custom_handler(exc, ctx):
            nonlocal custom_called
            custom_called = True
            return "handled"
        
        handler.register_handler(ValueError, custom_handler)
        
        result = handler.handle(ValueError("test"))
        assert custom_called
        assert result == "handled"
    
    @pytest.mark.asyncio
    async def test_execute_with_circuit_breaker(self):
        handler = ErrorHandler()
        
        async def func():
            return "success"
        
        result = await handler.execute_with_circuit_breaker(func)
        assert result == "success"
    
    def test_handler_decorator(self):
        call_count = 0
        
        @with_error_handler(retry=False, circuit_breaker=False)
        async def decorated_func():
            nonlocal call_count
            call_count += 1
            return "result"
        
        # Note: decorator returns wrapper, need to run in async context
        assert asyncio.iscoroutinefunction(decorated_func)


class TestErrorContext:
    """Test error context data structure."""
    
    def test_error_context_creation(self):
        ctx = ErrorContext(
            error_type="ValueError",
            classification=ErrorClassification.VALIDATION_ERROR,
            message="Invalid value"
        )
        
        assert ctx.error_type == "ValueError"
        assert ctx.classification == ErrorClassification.VALIDATION_ERROR
        assert ctx.message == "Invalid value"
        assert ctx.retry_count == 0
        assert ctx.metadata == {}
    
    def test_error_context_with_metadata(self):
        ctx = ErrorContext(
            error_type="TimeoutError",
            classification=ErrorClassification.NETWORK_TIMEOUT,
            message="Request timed out",
            component="api_client",
            metadata={"url": "https://example.com", "method": "GET"}
        )
        
        assert ctx.component == "api_client"
        assert ctx.metadata["url"] == "https://example.com"


class TestRetryConfig:
    """Test retry configuration."""
    
    def test_default_config(self):
        config = RetryConfig()
        
        assert config.max_retries == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
    
    def test_custom_config(self):
        config = RetryConfig(
            max_retries=5,
            base_delay=0.5,
            max_delay=30.0,
            exponential_base=1.5,
            jitter=False
        )
        
        assert config.max_retries == 5
        assert config.base_delay == 0.5
        assert config.jitter is False


class TestIntegration:
    """Integration tests for error handling framework."""
    
    @pytest.mark.asyncio
    async def test_full_retry_with_backoff_timing(self):
        """Test that exponential backoff actually delays."""
        handler = ErrorHandler(
            retry_config=RetryConfig(
                max_retries=2,
                base_delay=0.1,
                max_delay=1.0,
                jitter=False
            )
        )
        
        call_times = []
        
        async def func():
            call_times.append(time.time())
            if len(call_times) < 3:
                raise TimeoutError("Temporary")
            return "success"
        
        start = time.time()
        result = await handler.execute_with_retry(func)
        elapsed = time.time() - start
        
        assert result == "success"
        assert len(call_times) == 3
        # Should have at least 0.1s delay between calls
        assert elapsed >= 0.2
    
    @pytest.mark.asyncio
    async def test_circuit_breaker_prevents_cascading_failures(self):
        """Test that circuit breaker prevents excessive calls to failing service."""
        cb = CircuitBreaker(CircuitBreakerConfig(
            failure_threshold=2,
            recovery_timeout=10.0  # Long recovery
        ))
        
        call_count = 0
        
        async def failing_service():
            nonlocal call_count
            call_count += 1
            raise Exception("Service unavailable")
        
        # First two calls should go through and fail
        for _ in range(2):
            with pytest.raises(Exception):
                await cb.call(failing_service)
        
        assert call_count == 2
        assert cb.state == CircuitBreakerState.OPEN
        
        # Next calls should be rejected immediately without calling service
        for _ in range(5):
            with pytest.raises(CircuitBreakerOpenError):
                await cb.call(failing_service)
        
        # Service should not be called again
        assert call_count == 2


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
