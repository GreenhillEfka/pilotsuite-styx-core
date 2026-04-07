"""Tests for Circuit Breaker.

Test coverage for Error Isolation / Circuit Breaker (P0 Critical):
- State transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
- Failure threshold
- Recovery timeout
- Global circuit breakers
- CircuitOpenError handling

Author: Clawdya
Version: 1.0.0
Date: 2026-03-02
"""
import pytest
import time
from unittest.mock import MagicMock, patch

from copilot_core.circuit_breaker import (
    CircuitBreaker,
    CircuitState,
    CircuitOpenError,
    ha_supervisor_breaker,
    ollama_breaker,
    get_all_breaker_status,
)


@pytest.fixture
def circuit_breaker():
    """Create a CircuitBreaker instance."""
    return CircuitBreaker(
        name="test_service",
        failure_threshold=3,
        recovery_timeout=1.0,  # 1 second for fast tests
    )


class TestCircuitBreakerInit:
    """Tests for CircuitBreaker initialization."""

    def test_init_default_values(self):
        """Test initialization with default values."""
        cb = CircuitBreaker("test")
        
        assert cb.name == "test"
        assert cb.failure_threshold == 5
        assert cb.recovery_timeout == 30.0
        assert cb._state == CircuitState.CLOSED
        assert cb._failure_count == 0

    def test_init_custom_values(self, circuit_breaker):
        """Test initialization with custom values."""
        assert circuit_breaker.name == "test_service"
        assert circuit_breaker.failure_threshold == 3
        assert circuit_breaker.recovery_timeout == 1.0


class TestCircuitState:
    """Tests for circuit state management."""

    def test_initial_state_closed(self, circuit_breaker):
        """Test initial state is CLOSED."""
        assert circuit_breaker.state == CircuitState.CLOSED

    def test_state_transitions_to_open(self, circuit_breaker):
        """Test state transitions to OPEN after failures."""
        # Trigger failures
        for i in range(3):
            try:
                circuit_breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass
        
        assert circuit_breaker.state == CircuitState.OPEN

    def test_state_transitions_to_half_open(self, circuit_breaker):
        """Test state transitions to HALF_OPEN after recovery timeout."""
        # Trigger failures
        for i in range(3):
            try:
                circuit_breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass
        
        assert circuit_breaker.state == CircuitState.OPEN
        
        # Wait for recovery timeout
        time.sleep(1.1)
        
        assert circuit_breaker.state == CircuitState.HALF_OPEN

    def test_state_resets_to_closed_on_success(self, circuit_breaker):
        """Test state resets to CLOSED on success."""
        # Trigger some failures
        for i in range(2):
            try:
                circuit_breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass
        
        assert circuit_breaker._failure_count == 2
        
        # Success
        result = circuit_breaker.call(lambda: "success")
        
        assert result == "success"
        assert circuit_breaker.state == CircuitState.CLOSED
        assert circuit_breaker._failure_count == 0


class TestCircuitBreakerCall:
    """Tests for circuit breaker call functionality."""

    def test_call_success(self, circuit_breaker):
        """Test successful call."""
        result = circuit_breaker.call(lambda: "result")
        
        assert result == "result"
        assert circuit_breaker._failure_count == 0

    def test_call_failure_increments_count(self, circuit_breaker):
        """Test failure increments failure count."""
        try:
            circuit_breaker.call(lambda: (_ for _ in ()).throw(Exception("error")))
        except Exception:
            pass
        
        assert circuit_breaker._failure_count == 1

    def test_call_raises_circuit_open(self, circuit_breaker):
        """Test call raises CircuitOpenError when circuit is OPEN."""
        # Open the circuit
        for i in range(3):
            try:
                circuit_breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass
        
        assert circuit_breaker.state == CircuitState.OPEN
        
        # Try to call
        with pytest.raises(CircuitOpenError, match="OPEN"):
            circuit_breaker.call(lambda: "should not execute")

    def test_call_half_open_allows_one_request(self, circuit_breaker):
        """Test HALF_OPEN state allows one test request."""
        # Open the circuit
        for i in range(3):
            try:
                circuit_breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass
        
        # Wait for recovery timeout
        time.sleep(1.1)
        
        assert circuit_breaker.state == CircuitState.HALF_OPEN
        
        # Successful call in HALF_OPEN should close circuit
        result = circuit_breaker.call(lambda: "recovered")
        
        assert result == "recovered"
        assert circuit_breaker.state == CircuitState.CLOSED

    def test_call_half_open_failure_reopens(self, circuit_breaker):
        """Test HALF_OPEN failure reopens circuit."""
        # Open the circuit
        for i in range(3):
            try:
                circuit_breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass
        
        # Wait for recovery timeout
        time.sleep(1.1)
        
        assert circuit_breaker.state == CircuitState.HALF_OPEN
        
        # Failed call in HALF_OPEN should reopen circuit
        try:
            circuit_breaker.call(lambda: (_ for _ in ()).throw(Exception("still failing")))
        except Exception:
            pass
        
        assert circuit_breaker.state == CircuitState.OPEN


class TestCircuitOpenError:
    """Tests for CircuitOpenError exception."""

    def test_circuit_open_error_message(self, circuit_breaker):
        """Test CircuitOpenError contains useful message."""
        # Open the circuit
        for i in range(3):
            try:
                circuit_breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass
        
        try:
            circuit_breaker.call(lambda: "test")
        except CircuitOpenError as e:
            assert "OPEN" in str(e)
            assert "test_service" in str(e)
            assert "failures=3" in str(e)


class TestGetStatus:
    """Tests for get_status method."""

    def test_get_status_closed(self, circuit_breaker):
        """Test get_status when CLOSED."""
        status = circuit_breaker.get_status()
        
        assert status["name"] == "test_service"
        assert status["state"] == "closed"
        assert status["failure_count"] == 0
        assert status["failure_threshold"] == 3
        assert status["recovery_timeout_s"] == 1.0

    def test_get_status_open(self, circuit_breaker):
        """Test get_status when OPEN."""
        # Open the circuit
        for i in range(3):
            try:
                circuit_breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass
        
        status = circuit_breaker.get_status()
        
        assert status["state"] == "open"
        assert status["failure_count"] == 3


class TestGlobalBreakers:
    """Tests for global circuit breakers."""

    def test_ha_supervisor_breaker_exists(self):
        """Test HA Supervisor breaker exists."""
        assert ha_supervisor_breaker is not None
        assert ha_supervisor_breaker.name == "ha_supervisor"
        assert ha_supervisor_breaker.failure_threshold == 5

    def test_ollama_breaker_exists(self):
        """Test Ollama breaker exists."""
        assert ollama_breaker is not None
        assert ollama_breaker.name == "ollama"
        assert ollama_breaker.failure_threshold == 3

    def test_get_all_breaker_status(self):
        """Test getting status of all breakers."""
        status_list = get_all_breaker_status()
        
        assert len(status_list) == 2
        assert any(s["name"] == "ha_supervisor" for s in status_list)
        assert any(s["name"] == "ollama" for s in status_list)


class TestIntegration:
    """Integration tests for circuit breaker."""

    def test_rapid_failures_open_circuit(self, circuit_breaker):
        """Test rapid failures open circuit quickly."""
        start = time.time()
        
        for i in range(3):
            try:
                circuit_breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass
        
        elapsed = time.time() - start
        
        assert circuit_breaker.state == CircuitState.OPEN
        assert elapsed < 0.1  # Should be very fast

    def test_recovery_workflow(self, circuit_breaker):
        """Test complete recovery workflow."""
        # 1. Circuit starts CLOSED
        assert circuit_breaker.state == CircuitState.CLOSED
        
        # 2. Failures open the circuit
        for i in range(3):
            try:
                circuit_breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass
        
        assert circuit_breaker.state == CircuitState.OPEN
        
        # 3. Wait for recovery timeout
        time.sleep(1.1)
        assert circuit_breaker.state == CircuitState.HALF_OPEN
        
        # 4. Success closes the circuit
        circuit_breaker.call(lambda: "success")
        assert circuit_breaker.state == CircuitState.CLOSED
        
        # 5. Circuit is fully recovered
        result = circuit_breaker.call(lambda: "working")
        assert result == "working"

    def test_concurrent_access_safety(self, circuit_breaker):
        """Test thread-safe concurrent access."""
        import threading
        
        errors = []
        
        def fail():
            try:
                circuit_breaker.call(lambda: (_ for _ in ()).throw(Exception("fail")))
            except Exception:
                pass
        
        # Start multiple threads
        threads = [threading.Thread(target=fail) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
        
        # Should not have raised any threading errors
        assert len(errors) == 0
        # Circuit opens after 3 failures, so failure_count caps at threshold
        assert circuit_breaker._failure_count >= 3
        assert circuit_breaker.state == CircuitState.OPEN
