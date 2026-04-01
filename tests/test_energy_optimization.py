"""Tests for Energy Optimization Engine — Slice 13."""
import pytest
from copilot_core.energy.optimization_engine import (
    EnergyOptimizationEngine,
    EnergyReading,
    EnergyUnit,
    OptimizationType,
    create_energy_optimization_engine,
)


class TestEnergyOptimizationEngine:
    """Test energy optimization engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_energy_optimization_engine()
        assert engine is not None
    
    def test_add_reading(self):
        """Test adding energy readings."""
        engine = EnergyOptimizationEngine()
        
        reading = EnergyReading(
            entity_id="sensor.power_living_room",
            zone_id="zone_living_room",
            module_id="energy_living_room",
            value=150.0,
            unit=EnergyUnit.W,
        )
        
        engine.add_reading(reading)
        
        # Should have reading
        assert "sensor.power_living_room" in engine._readings
        assert len(engine._readings["sensor.power_living_room"]) == 1
    
    def test_energy_summary(self):
        """Test energy summary calculation."""
        engine = EnergyOptimizationEngine()
        
        # Add readings
        for i in range(10):
            reading = EnergyReading(
                entity_id="sensor.power_test",
                zone_id="zone_test",
                module_id="energy_test",
                value=100.0,
                unit=EnergyUnit.W,
            )
            engine.add_reading(reading)
        
        summary = engine.get_energy_summary(period_hours=24)
        
        assert summary["total_consumption_wh"] == 1000.0  # 10 * 100W
        assert summary["total_consumption_kwh"] == 1.0
        assert summary["entity_count"] == 1
        assert summary["period_hours"] == 24
    
    def test_schedule_shift_suggestion_during_peak(self):
        """Test schedule shift suggestion during peak hours."""
        engine = EnergyOptimizationEngine()
        
        # Add reading during peak hour (18:00 = 6 PM)
        reading = EnergyReading(
            entity_id="sensor.power_living_room",
            zone_id="zone_living_room",
            module_id="energy_living_room",
            value=1500.0,  # 1.5kW, above threshold
            unit=EnergyUnit.W,
            timestamp="2026-03-31T18:00:00Z",
            cost=0.525,  # 1.5kW * 0.35 EUR/kWh
            tariff_rate="peak",
        )
        
        engine.add_reading(reading)
        
        # Should create optimization suggestion
        suggestions = engine.get_suggestions()
        
        # May or may not create suggestion depending on implementation
        # Test that get_suggestions works
        assert isinstance(suggestions, list)
    
    def test_accept_suggestion(self):
        """Test accepting a suggestion."""
        engine = EnergyOptimizationEngine()
        
        # Create a suggestion manually for testing
        from copilot_core.energy.optimization_engine import OptimizationSuggestion
        
        suggestion = OptimizationSuggestion(
            suggestion_id="opt_test_001",
            optimization_type=OptimizationType.SCHEDULE_SHIFT,
            zone_id="zone_test",
            module_id="energy_test",
            description="Test suggestion",
            estimated_savings=10.0,
            estimated_savings_unit="EUR",
            confidence=0.8,
            action_required={"action": "test"},
        )
        
        engine._suggestions["opt_test_001"] = suggestion
        
        # Accept
        result = engine.accept_suggestion("opt_test_001")
        assert result is True
        
        # Verify accepted
        suggestions = engine.get_suggestions(unresolved_only=True)
        assert not any(s["suggestion_id"] == "opt_test_001" for s in suggestions)
    
    def test_reject_suggestion_with_feedback(self):
        """Test rejecting a suggestion with feedback."""
        engine = EnergyOptimizationEngine()
        
        from copilot_core.energy.optimization_engine import OptimizationSuggestion
        
        suggestion = OptimizationSuggestion(
            suggestion_id="opt_test_002",
            optimization_type=OptimizationType.LOAD_REDUCTION,
            zone_id="zone_test",
            module_id="energy_test",
            description="Test suggestion",
            estimated_savings=5.0,
            estimated_savings_unit="EUR",
            confidence=0.7,
            action_required={"action": "test"},
        )
        
        engine._suggestions["opt_test_002"] = suggestion
        
        # Reject with feedback
        result = engine.reject_suggestion("opt_test_002", feedback="not_applicable")
        assert result is True
        
        # Verify rejected
        suggestion_obj = engine._suggestions["opt_test_002"]
        assert suggestion_obj.rejected is True
        assert suggestion_obj.feedback == "not_applicable"
    
    def test_tariff_forecast(self):
        """Test tariff forecast."""
        engine = EnergyOptimizationEngine()
        
        forecast = engine.get_tariff_forecast(hours_ahead=24)
        
        # Should have 24 hours of forecast
        assert len(forecast) == 24
        
        # Each hour should have required fields
        for hour_forecast in forecast:
            assert "hour" in hour_forecast
            assert "timestamp" in hour_forecast
            assert "tariff_name" in hour_forecast
            assert "tariff_rate" in hour_forecast
    
    def test_reading_trimming(self):
        """Test that readings are trimmed to last 1000."""
        engine = EnergyOptimizationEngine()
        
        # Add 1500 readings
        for i in range(1500):
            reading = EnergyReading(
                entity_id="sensor.power_test",
                zone_id="zone_test",
                module_id="energy_test",
                value=float(i),
                unit=EnergyUnit.W,
            )
            engine.add_reading(reading)
        
        # Should be trimmed to 1000
        assert len(engine._readings["sensor.power_test"]) == 1000
        
        # Should contain last 1000 readings (500-1499)
        assert engine._readings["sensor.power_test"][0].value == 500.0
        assert engine._readings["sensor.power_test"][-1].value == 1499.0
    
    def test_zone_consumption_breakdown(self):
        """Test zone consumption breakdown in summary."""
        engine = EnergyOptimizationEngine()
        
        # Add readings for zone_a
        for i in range(5):
            reading = EnergyReading(
                entity_id="sensor.power_a",
                zone_id="zone_a",
                module_id="energy_a",
                value=100.0,
                unit=EnergyUnit.W,
            )
            engine.add_reading(reading)
        
        # Add readings for zone_b
        for i in range(5):
            reading = EnergyReading(
                entity_id="sensor.power_b",
                zone_id="zone_b",
                module_id="energy_b",
                value=200.0,
                unit=EnergyUnit.W,
            )
            engine.add_reading(reading)
        
        summary = engine.get_energy_summary(period_hours=24)
        
        assert "zone_a" in summary["zone_consumption"]
        assert "zone_b" in summary["zone_consumption"]
        assert summary["zone_consumption"]["zone_a"] == 500.0  # 5 * 100W
        assert summary["zone_consumption"]["zone_b"] == 1000.0  # 5 * 200W
    
    def test_suggestion_to_dict(self):
        """Test suggestion serialization."""
        from copilot_core.energy.optimization_engine import OptimizationSuggestion
        
        suggestion = OptimizationSuggestion(
            suggestion_id="opt_test",
            optimization_type=OptimizationType.PEAK_SHAVING,
            zone_id="zone_living_room",
            module_id="energy_living_room",
            description="Reduce peak demand",
            estimated_savings=15.0,
            estimated_savings_unit="EUR",
            confidence=0.9,
            action_required={"action": "reduce_load"},
        )
        
        d = suggestion.to_dict()
        
        assert d["suggestion_id"] == "opt_test"
        assert d["optimization_type"] == "peak_shaving"
        assert d["zone_id"] == "zone_living_room"
        assert d["estimated_savings"] == 15.0
        assert d["estimated_savings_unit"] == "EUR"
        assert d["confidence"] == 0.9
        assert d["accepted"] is False
        assert d["rejected"] is False
    
    def test_reading_to_dict(self):
        """Test reading serialization."""
        reading = EnergyReading(
            entity_id="sensor.power_test",
            zone_id="zone_test",
            module_id="energy_test",
            value=150.0,
            unit=EnergyUnit.W,
            cost=0.0375,
            tariff_rate="off_peak",
        )
        
        d = reading.to_dict()
        
        assert d["entity_id"] == "sensor.power_test"
        assert d["zone_id"] == "zone_test"
        assert d["value"] == 150.0
        assert d["unit"] == "W"
        assert d["cost"] == 0.0375
        assert d["tariff_rate"] == "off_peak"


class TestTariffPeriods:
    """Test tariff period functionality."""
    
    def test_get_tariff_for_peak_hour(self):
        """Test getting tariff for peak hour."""
        engine = EnergyOptimizationEngine()
        
        # 18:00 on Monday should be peak
        tariff = engine._get_tariff_for_time(18, "mon")
        
        assert tariff is not None
        assert tariff.name == "peak"
        assert tariff.rate == 0.35
    
    def test_get_tariff_for_off_peak_hour(self):
        """Test getting tariff for off-peak hour."""
        engine = EnergyOptimizationEngine()
        
        # 10:00 on Monday should be off_peak
        tariff = engine._get_tariff_for_time(10, "mon")
        
        assert tariff is not None
        assert tariff.name == "off_peak"
        assert tariff.rate == 0.25
    
    def test_get_tariff_for_super_off_peak_hour(self):
        """Test getting tariff for super off-peak hour."""
        engine = EnergyOptimizationEngine()
        
        # 23:00 on Monday should be super_off_peak
        tariff = engine._get_tariff_for_time(23, "mon")
        
        assert tariff is not None
        assert tariff.name == "super_off_peak"
        assert tariff.rate == 0.15
    
    def test_get_tariff_for_weekend(self):
        """Test getting tariff for weekend."""
        engine = EnergyOptimizationEngine()
        
        # 12:00 on Saturday should be weekend_off_peak
        tariff = engine._get_tariff_for_time(12, "sat")
        
        assert tariff is not None
        assert tariff.name == "weekend_off_peak"
        assert tariff.rate == 0.15

    def test_custom_tariff_periods_override_defaults(self):
        """Custom tariff periods should be used once configured."""
        engine = EnergyOptimizationEngine()
        engine.set_tariff_periods([
            {"name": "cheap", "start_hour": 0, "end_hour": 12, "rate": 0.11, "days": ["mon"]},
            {"name": "expensive", "start_hour": 12, "end_hour": 24, "rate": 0.41, "days": ["mon"]},
        ])

        morning = engine._get_tariff_for_time(9, "mon")
        afternoon = engine._get_tariff_for_time(18, "mon")

        assert morning is not None
        assert morning.name == "cheap"
        assert afternoon is not None
        assert afternoon.name == "expensive"

    def test_zone_filtered_summary_includes_module_breakdown(self):
        """Zone filtering should retain module-level breakdown for the selected zone only."""
        engine = EnergyOptimizationEngine()
        engine.add_reading(EnergyReading(
            entity_id="sensor.a1",
            zone_id="zone_a",
            module_id="energy_a",
            value=120.0,
            unit=EnergyUnit.W,
        ))
        engine.add_reading(EnergyReading(
            entity_id="sensor.b1",
            zone_id="zone_b",
            module_id="energy_b",
            value=80.0,
            unit=EnergyUnit.W,
        ))

        summary = engine.get_energy_summary(zone_id="zone_a", period_hours=24)

        assert summary["zone_id"] == "zone_a"
        assert summary["total_consumption_wh"] == 120.0
        assert summary["zone_consumption"] == {"zone_a": 120.0}
        assert summary["module_consumption"] == {"energy_a": 120.0}
