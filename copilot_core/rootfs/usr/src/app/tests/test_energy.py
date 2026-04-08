"""Tests for Energy Neuron module."""

import pytest
import sys
import os

# Add the app directory to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../../../../..'))

from copilot_core.energy.service import EnergyService, EnergyAnomaly, ShiftingOpportunity, EnergySnapshot


class TestEnergyService:
    """Test EnergyService functionality."""
    
    def test_service_initialization(self):
        """Test EnergyService can be initialized without hass."""
        service = EnergyService()
        assert service is not None
        assert service.hass is None
        assert service._cache_ttl == 300
    
    def test_get_timestamp(self):
        """Test timestamp generation."""
        service = EnergyService()
        ts = service._get_timestamp()
        assert ts.endswith('Z')
        assert 'T' in ts
    
    def test_generate_id(self):
        """Test ID generation."""
        service = EnergyService()
        id1 = service._generate_id("test")
        id2 = service._generate_id("test")
        assert id1.startswith("test_")
        assert len(id1) == 13  # prefix(5) + 8 char hash
        # IDs should be unique
        assert id1 != id2
    
    def test_get_baselines(self):
        """Test baseline retrieval."""
        service = EnergyService()
        baselines = service._get_baselines()
        assert "washer" in baselines
        assert "dryer" in baselines
        assert "dishwasher" in baselines
        assert "ev_charger" in baselines
        assert "heat_pump" in baselines
        assert "hvac" in baselines
    
    def test_get_energy_snapshot_without_hass(self):
        """Test snapshot generation without HA."""
        service = EnergyService()
        snapshot = service.get_energy_snapshot()
        assert isinstance(snapshot, EnergySnapshot)
        assert snapshot.total_consumption_today > 0
        assert snapshot.total_production_today >= 0
        assert snapshot.current_power >= 0
        assert snapshot.peak_power_today > 0
    
    def test_detect_anomalies_without_hass(self):
        """Test anomaly detection without HA."""
        service = EnergyService()
        anomalies = service.detect_anomalies()
        assert isinstance(anomalies, list)
        # Without hass, we get aggregate anomaly check
        for anomaly in anomalies:
            assert isinstance(anomaly, EnergyAnomaly)
            assert anomaly.severity in ["low", "medium", "high"]
    
    def test_detect_shifting_opportunities(self):
        """Test load shifting opportunity detection."""
        service = EnergyService()
        opportunities = service.detect_shifting_opportunities()
        assert isinstance(opportunities, list)
        for opp in opportunities:
            assert isinstance(opp, ShiftingOpportunity)
            assert opp.device_type in ["dishwasher", "ev_charger", "washer"]
            assert opp.reason in ["solar_oversupply", "off_peak_pricing", "avoid_peak_pricing"]
            assert 0 <= opp.confidence <= 1
    
    def test_explain_suggestion_unknown(self):
        """Test explanation for unknown suggestion."""
        service = EnergyService()
        explanation = service.explain_suggestion("unknown_id")
        assert explanation["type"] == "unknown"
        assert explanation["type"] == "unknown"
    
    def test_explain_suggestion_anomaly(self):
        """Test explanation for anomaly suggestion."""
        service = EnergyService()
        # Get first anomaly
        anomalies = service.detect_anomalies()
        if anomalies:
            explanation = service.explain_suggestion(anomalies[0].id)
            assert explanation["type"] in ["anomaly", "unknown"]
    
    def test_get_suppression_status(self):
        """Test suppression status check."""
        service = EnergyService()
        status = service.get_suppression_status()
        assert "suppressed" in status
        assert isinstance(status["suppressed"], bool)
        assert "reason" in status
    
    def test_get_health(self):
        """Test health check."""
        service = EnergyService()
        health = service.get_health()
        assert health["status"] == "healthy"
        assert health["cache_valid"] == False  # Not yet updated
        assert "baselines_configured" in health
        assert "anomaly_thresholds" in health
    
    def test_cache_invalid_initially(self):
        """Test cache is invalid on init."""
        service = EnergyService()
        assert service._is_cache_valid() == False
    
    def test_cache_valid_after_update(self):
        """Test cache becomes valid after update."""
        service = EnergyService()
        service.get_energy_snapshot()
        assert service._is_cache_valid() == True
    
    def test_anomaly_severity_levels(self):
        """Test anomaly severity classification."""
        service = EnergyService()
        anomalies = service.detect_anomalies()
        for anomaly in anomalies:
            if abs(anomaly.deviation_percent) >= 50:
                assert anomaly.severity == "high"
            elif abs(anomaly.deviation_percent) >= 30:
                assert anomaly.severity in ["high", "medium"]
            elif abs(anomaly.deviation_percent) >= 15:
                assert anomaly.severity in ["low", "medium", "high"]
    
    def test_shifting_confidence_range(self):
        """Test shifting opportunities have valid confidence."""
        service = EnergyService()
        opportunities = service.detect_shifting_opportunities()
        for opp in opportunities:
            assert 0 <= opp.confidence <= 1
    
    def test_shifting_cost_values(self):
        """Test shifting opportunities have valid cost values."""
        service = EnergyService()
        opportunities = service.detect_shifting_opportunities()
        for opp in opportunities:
            assert opp.current_cost >= 0
            assert opp.optimal_cost >= 0
            assert opp.savings_estimate >= 0


class TestEnergyDataclasses:
    """Test Energy dataclasses."""
    
    def test_energy_snapshot(self):
        """Test EnergySnapshot dataclass."""
        snapshot = EnergySnapshot(
            timestamp="2024-01-01T00:00:00Z",
            total_consumption_today=15.5,
            total_production_today=5.2,
            current_power=850.0,
            peak_power_today=2500.0,
            anomalies_detected=2,
            shifting_opportunities=1,
            baselines={"washer": 1.5, "dryer": 3.5}
        )
        assert snapshot.total_consumption_today == 15.5
        assert snapshot.current_power == 850.0
    
    def test_energy_anomaly(self):
        """Test EnergyAnomaly dataclass."""
        anomaly = EnergyAnomaly(
            id="test_12345678",
            timestamp="2024-01-01T00:00:00Z",
            device_id="sensor.washer_energy",
            device_type="washer",
            expected_value=1.5,
            actual_value=2.5,
            deviation_percent=66.67,
            severity="high",
            description="Washer consumption 66.7% above expected"
        )
        assert anomaly.severity == "high"
        assert anomaly.deviation_percent == 66.67
    
    def test_shifting_opportunity(self):
        """Test ShiftingOpportunity dataclass."""
        opp = ShiftingOpportunity(
            id="shift_12345678",
            timestamp="2024-01-01T00:00:00Z",
            device_type="dishwasher",
            reason="solar_oversupply",
            current_cost=0.30,
            optimal_cost=0.0,
            savings_estimate=0.42,
            suggested_time_window=("2024-01-01T00:00:00Z", "2024-01-01T03:00:00Z"),
            confidence=0.85
        )
        assert opp.reason == "solar_oversupply"
        assert opp.confidence == 0.85


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
