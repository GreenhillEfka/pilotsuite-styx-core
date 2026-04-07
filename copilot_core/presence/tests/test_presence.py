"""Presence Tests — Bayesian Presence Detection test suite."""
from __future__ import annotations

import pytest
import time
from typing import Dict, Any


class TestWilsonScoreInterval:
    """Test Wilson Score Interval calculations."""

    @pytest.fixture
    def wilson(self):
        from copilot_core.presence.wilson_score import WilsonScoreInterval
        return WilsonScoreInterval(confidence_level=0.95)

    def test_wilson_zero_trials(self, wilson):
        """Test Wilson with zero trials."""
        result = wilson.calculate(0, 0)
        
        assert result.observed_ratio == 0.0
        assert result.lower_bound == 0.0
        assert result.upper_bound == 1.0
        assert result.confidence == 0.0

    def test_wilson_all_successes(self, wilson):
        """Test Wilson with all successes."""
        result = wilson.calculate(10, 10)
        
        assert result.observed_ratio == 1.0
        assert result.lower_bound > 0.7  # Should be high
        assert result.upper_bound == 1.0

    def test_wilson_all_failures(self, wilson):
        """Test Wilson with all failures."""
        result = wilson.calculate(0, 10)
        
        assert result.observed_ratio == 0.0
        assert result.lower_bound == 0.0
        assert result.upper_bound < 0.3  # Should be low

    def test_wilson_mixed(self, wilson):
        """Test Wilson with mixed results."""
        result = wilson.calculate(7, 10)
        
        assert result.observed_ratio == 0.7
        assert 0.4 < result.lower_bound < 0.9
        assert 0.4 < result.upper_bound < 1.0

    def test_wilson_confidence_increases_with_samples(self, wilson):
        """Test that confidence increases with sample size."""
        result1 = wilson.calculate(5, 10)
        result2 = wilson.calculate(50, 100)
        
        assert result2.confidence > result1.confidence

    def test_bayesian_update(self, wilson):
        """Test Bayesian update with Beta prior."""
        posterior = wilson.bayesian_update(
            prior_alpha=2.0,
            prior_beta=2.0,
            successes=8,
            trials=10,
        )
        
        assert "posterior" in posterior
        assert posterior["posterior"]["alpha"] == 10.0  # 2 + 8
        assert posterior["posterior"]["beta"] == 4.0  # 2 + (10-8)
        assert 0.5 < posterior["mean"] < 0.9


class TestMultiSensorFusion:
    """Test multi-sensor fusion."""

    @pytest.fixture
    def fusion(self):
        from copilot_core.presence.sensor_fusion import MultiSensorFusion
        return MultiSensorFusion()

    def test_fusion_no_readings(self, fusion):
        """Test fusion with no readings."""
        result = fusion.fuse()
        
        assert result.is_present is False
        assert result.confidence == 0.0

    def test_fusion_single_sensor(self, fusion):
        """Test fusion with single sensor."""
        from copilot_core.presence.sensor_fusion import SensorReading, SensorType
        
        reading = SensorReading(
            sensor_type=SensorType.PIR,
            sensor_id="pir_1",
            value=0.9,
        )
        fusion.add_reading(reading)
        
        result = fusion.fuse()
        
        assert result.is_present is True
        assert result.confidence > 0.5

    def test_fusion_multiple_sensors(self, fusion):
        """Test fusion with multiple sensors."""
        from copilot_core.presence.sensor_fusion import SensorReading, SensorType
        
        # Add conflicting sensors
        fusion.add_reading(SensorReading(SensorType.PIR, "pir_1", 1.0))
        fusion.add_reading(SensorReading(SensorType.RADAR, "radar_1", 0.0))
        
        result = fusion.fuse()
        
        # Should be somewhere in between
        assert 0.0 < result.confidence < 1.0

    def test_fusion_time_decay(self, fusion):
        """Test that old readings decay."""
        from copilot_core.presence.sensor_fusion import SensorReading, SensorType
        
        # Add old reading
        old_reading = SensorReading(SensorType.PIR, "pir_1", 1.0)
        old_reading.timestamp = time.time() - 120  # 2 minutes ago
        fusion._recent_readings.append(old_reading)
        
        # Add new reading
        fusion.add_reading(SensorReading(SensorType.RADAR, "radar_1", 1.0))
        
        result = fusion.fuse()
        
        # Old reading should have less weight
        assert "pir" in result.sensor_contributions
        assert "radar" in result.sensor_contributions

    def test_sensor_health(self, fusion):
        """Test sensor health reporting."""
        from copilot_core.presence.sensor_fusion import SensorReading, SensorType
        
        fusion.add_reading(SensorReading(SensorType.PIR, "pir_1", 0.8))
        fusion.add_reading(SensorReading(SensorType.PIR, "pir_1", 0.9))
        
        health = fusion.get_sensor_health()
        
        assert "pir" in health
        assert health["pir"]["reading_count"] == 2


class TestPresenceAPI:
    """Test Presence API v2."""

    @pytest.fixture
    def presence_api(self):
        from copilot_core.presence.api import PresenceAPI
        return PresenceAPI()

    def test_update_sensor(self, presence_api):
        """Test sensor update."""
        state = presence_api.update_sensor(
            sensor_type="pir",
            sensor_id="pir_1",
            value=0.9,
        )
        
        assert state.is_present is True
        assert state.confidence > 0.5
        assert state.sensor_count == 1

    def test_get_current_state(self, presence_api):
        """Test getting current state."""
        state = presence_api.get_current_state()
        
        assert hasattr(state, 'is_present')
        assert hasattr(state, 'confidence')
        assert hasattr(state, 'wilson_lower')
        assert hasattr(state, 'wilson_upper')

    def test_presence_history(self, presence_api):
        """Test presence history."""
        # Add some updates
        for i in range(10):
            presence_api.update_sensor("pir", f"pir_{i}", 0.8 if i % 2 == 0 else 0.2)
        
        history = presence_api.get_presence_history(limit=5)
        
        assert len(history) == 5
        assert all("timestamp" in h for h in history)
        assert all("state" in h for h in history)

    def test_sensor_health_via_api(self, presence_api):
        """Test sensor health via API."""
        presence_api.update_sensor("pir", "pir_1", 0.9)
        presence_api.update_sensor("radar", "radar_1", 0.8)
        
        health = presence_api.get_sensor_health()
        
        assert "pir" in health
        assert "radar" in health

    def test_stats(self, presence_api):
        """Test API statistics."""
        presence_api.update_sensor("pir", "pir_1", 0.9)
        
        stats = presence_api.get_stats()
        
        assert stats["total_updates"] >= 1
        assert "current_presence" in stats


# Run with: pytest copilot_core/presence/tests/test_presence.py -v
