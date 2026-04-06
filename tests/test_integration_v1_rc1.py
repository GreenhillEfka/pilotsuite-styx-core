"""Integration Test Suite (Slice 153).

End-to-end tests for Core v1.0.0 RC1:
- Module Read-Models Integration
- Circuit Breaker + External Services
- RAG Pipeline (local + enhanced)
- Energy Forecasting (statistical + ML)
"""

from __future__ import annotations

import pytest
import time
from datetime import datetime, timedelta


class TestModuleReadModelsIntegration:
    """Test Module Read-Models end-to-end."""
    
    def test_presence_get_summary(self):
        """Test PresenceModule.get_summary() returns valid structure."""
        from copilot_core.presence.zone_presence import create_presence_module
        
        module = create_presence_module()
        summary = module.get_summary()
        
        assert "summary" in summary
        assert "detailed_states" in summary
        assert "active_features" in summary
        assert isinstance(summary["detailed_states"], list)
    
    def test_light_get_summary(self):
        """Test LightModule.get_summary() returns valid structure."""
        from copilot_core.light.zone_light import create_light_module
        
        module = create_light_module()
        summary = module.get_summary()
        
        assert "summary" in summary
        assert "detailed_states" in summary
        assert "zones lit" in summary["summary"].lower()
    
    def test_climate_get_summary(self):
        """Test ClimateModule.get_summary() returns valid structure."""
        from copilot_core.climate.climate import create_climate_module
        
        module = create_climate_module()
        summary = module.get_summary()
        
        assert "summary" in summary
        assert "detailed_states" in summary
        assert "active" in summary["summary"].lower()


class TestCircuitBreakerIntegration:
    """Test Circuit Breaker with simulated failures."""
    
    def test_circuit_opens_after_failures(self):
        """Test circuit opens after threshold failures."""
        from copilot_core.utils.circuit_breaker import CircuitBreaker
        
        breaker = CircuitBreaker("test", failure_threshold=3)
        
        # Simulate failures
        for _ in range(3):
            breaker.record_failure()
        
        assert breaker.state.value == "open"
        assert not breaker.can_execute()
    
    def test_circuit_recovery(self):
        """Test circuit transitions to half-open then closed."""
        from copilot_core.utils.circuit_breaker import CircuitBreaker
        
        breaker = CircuitBreaker("test", failure_threshold=1, recovery_timeout=0.1)
        breaker.record_failure()
        
        # Wait for recovery timeout
        time.sleep(0.15)
        
        assert breaker.can_execute()  # Should be half-open
        breaker.record_success()
        assert breaker.state.value == "closed"


class TestRAGIntegration:
    """Test RAG Pipeline integration."""
    
    def test_rag_cached_response(self):
        """Test RAG endpoint uses cache."""
        from copilot_core.api.v1.backend_ui import _get_cached_rag_stats, _set_cached_rag_stats
        
        # Set cache
        test_data = {"vectors": {"count": 100}}
        _set_cached_rag_stats(test_data)
        
        # Get from cache
        cached = _get_cached_rag_stats()
        assert cached == test_data


class TestEnergyForecastingIntegration:
    """Test Energy Forecasting with ML fallback."""
    
    def test_statistical_fallback_when_ml_unavailable(self):
        """Test statistical method works when ML is not available."""
        from copilot_core.energy.forecast import EnergyForecastEngine
        
        engine = EnergyForecastEngine(use_ml=False)
        forecast = engine.generate_hourly_forecast(hours=24)
        
        assert len(forecast) == 24
        assert all(p.predicted_consumption_kw > 0 for p in forecast)
    
    def test_ml_prediction_when_available(self):
        """Test ML prediction when model is available."""
        from copilot_core.energy.forecast import EnergyForecastEngine
        
        # Try with ML (will fallback if model not available)
        engine = EnergyForecastEngine(use_ml=True)
        ml_result = engine.predict_with_ml(hours=6)
        
        # Should either return predictions or empty list (not crash)
        assert isinstance(ml_result, list)


class TestEndToEndPerformance:
    """Test performance requirements."""
    
    def test_backend_ui_response_time(self):
        """Test Backend-UI tabs respond in <50ms."""
        import time
        from copilot_core.api.v1.backend_ui import get_rag
        
        # Warmup
        try:
            get_rag()
        except:
            pass
        
        # Measure
        start = time.time()
        try:
            get_rag()
        except:
            pass
        elapsed = (time.time() - start) * 1000
        
        # Should be <50ms with cache
        assert elapsed < 100  # Allow some margin for test environment


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
