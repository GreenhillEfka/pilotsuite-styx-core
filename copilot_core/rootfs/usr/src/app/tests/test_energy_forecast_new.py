"""Tests for Energy Forecast Module (v12.6.0).

Tests for:
- EnergyForecastEngine (Verbrauchsprognose)
- PVPredictionEngine (PV-Ertragsprognose)
- LoadShiftingEngine (Lastverlagerung)
"""

import pytest
from datetime import datetime, timedelta

from copilot_core.energy.forecast import (
    EnergyForecastEngine,
    ForecastDataPoint,
    DailyForecast,
    ForecastSummary,
)
from copilot_core.energy.pv_prediction import (
    PVPredictionEngine,
    PVHourlyForecast,
    PVDailyForecast,
    PVForecastSummary,
)
from copilot_core.energy.load_shifting import (
    LoadShiftingEngine,
    ShiftableDevice,
    LoadShiftRecommendation,
    OptimizationWindow,
    LoadShiftSummary,
)


# ──────────────────────────────────────────────────────────────────────────
# EnergyForecastEngine Tests
# ──────────────────────────────────────────────────────────────────────────

class TestEnergyForecastEngine:
    """Tests for EnergyForecastEngine."""
    
    @pytest.fixture
    def engine(self):
        return EnergyForecastEngine(
            base_load_kw=0.3,
            latitude=52.52,
            longitude=13.405,
        )
    
    def test_initialization(self, engine):
        assert engine._base_load_kw == 0.3
        assert engine._lat == 52.52
        assert engine._lon == 13.405
    
    def test_set_base_load(self, engine):
        engine.set_base_load(0.5)
        assert engine._base_load_kw == 0.5
    
    def test_update_location(self, engine):
        engine.update_location(48.0, 11.0)
        assert engine._lat == 48.0
        assert engine._lon == 11.0
    
    def test_generate_hourly_forecast_default(self, engine):
        forecast = engine.generate_hourly_forecast(hours=24)
        assert len(forecast) == 24
        assert isinstance(forecast[0], ForecastDataPoint)
    
    def test_forecast_hours_sequential(self, engine):
        forecast = engine.generate_hourly_forecast(hours=48)
        # Hours should match the actual time of day, not sequential 0-47
        # (they wrap at midnight)
        assert len(forecast) == 48
        # Check timestamps are sequential
        for i in range(1, len(forecast)):
            t0 = datetime.fromisoformat(forecast[i-1].timestamp)
            t1 = datetime.fromisoformat(forecast[i].timestamp)
            assert (t1 - t0).total_seconds() == 3600
    
    def test_forecast_timestamps(self, engine):
        forecast = engine.generate_hourly_forecast(hours=24)
        now = datetime.now().replace(minute=0, second=0, microsecond=0)
        for i, point in enumerate(forecast):
            expected = now + timedelta(hours=i)
            assert point.timestamp[:13] == expected.isoformat()[:13]
    
    def test_consumption_values_positive(self, engine):
        forecast = engine.generate_hourly_forecast(hours=24)
        for point in forecast:
            assert point.predicted_consumption_kw > 0
            assert point.predicted_consumption_kwh > 0
    
    def test_confidence_range(self, engine):
        forecast = engine.generate_hourly_forecast(hours=24)
        for point in forecast:
            assert 0.3 <= point.confidence <= 0.98
    
    def test_day_type_assignment(self, engine):
        forecast = engine.generate_hourly_forecast(hours=48)
        day_types = set(p.day_type for p in forecast)
        # Should have at least weekday or weekend
        assert len(day_types) >= 1
        assert all(dt in ["weekday", "weekend"] for dt in day_types)
    
    def test_base_load_included(self, engine):
        forecast = engine.generate_hourly_forecast(hours=24)
        for point in forecast:
            assert point.base_load_kw == 0.3
            assert point.variable_load_kw >= 0
    
    def test_weather_adjustment(self, engine):
        weather_data = [{"temperature_c": 5.0} for _ in range(24)]  # Cold
        forecast = engine.generate_hourly_forecast(hours=24, weather_data=weather_data)
        for point in forecast:
            assert point.weather_adjustment >= 0  # Heating increases consumption
    
    def test_daily_forecast(self, engine):
        daily = engine.generate_daily_forecast(days=7)
        assert len(daily) == 7
        assert isinstance(daily[0], DailyForecast)
        assert len(daily[0].hourly_data) == 24
    
    def test_daily_forecast_totals(self, engine):
        daily = engine.generate_daily_forecast(days=1)
        day = daily[0]
        # Total should be sum of hourly
        hourly_sum = sum(h["predicted_consumption_kwh"] for h in day.hourly_data)
        assert abs(day.total_consumption_kwh - hourly_sum) < 0.1
    
    def test_summary_generation(self, engine):
        forecast = engine.generate_hourly_forecast(hours=48)
        summary = engine.generate_summary(forecast)
        assert isinstance(summary, ForecastSummary)
        assert summary.forecast_horizon_hours == 48
        assert summary.total_predicted_consumption_kwh > 0
        assert 0 <= summary.base_load_percentage <= 100
    
    def test_summary_price_range(self, engine):
        forecast = engine.generate_hourly_forecast(hours=48)
        summary = engine.generate_summary(forecast)
        assert summary.peak_consumption_kw >= summary.lowest_consumption_kw
    
    def test_dict_export(self, engine):
        result = engine.get_forecast_as_dict(hours=24)
        assert "generated_at" in result
        assert "summary" in result
        assert "hourly_forecast" in result
        assert "daily_forecast" in result
        assert len(result["hourly_forecast"]) == 24
    
    def test_historical_data_learning(self, engine):
        # Simulate historical data
        historical = []
        now = datetime.now()
        for h in range(168):  # 1 week
            ts = now - timedelta(hours=h)
            historical.append({
                "timestamp": ts.isoformat(),
                "consumption_kw": 0.5 + (ts.hour / 48),  # Simple pattern
            })
        
        engine.set_historical_data(historical)
        forecast = engine.generate_hourly_forecast(hours=24)
        
        # Should still generate valid forecast
        assert len(forecast) == 24
        assert all(p.predicted_consumption_kw > 0 for p in forecast)


# ──────────────────────────────────────────────────────────────────────────
# PVPredictionEngine Tests
# ──────────────────────────────────────────────────────────────────────────

class TestPVPredictionEngine:
    """Tests for PVPredictionEngine."""
    
    @pytest.fixture
    def pv_engine(self):
        return PVPredictionEngine(
            latitude=52.52,
            longitude=13.405,
            pv_peak_kw=10.0,
            panel_azimuth=180.0,
            panel_tilt=30.0,
        )
    
    def test_initialization(self, pv_engine):
        assert pv_engine._pv_peak == 10.0
        assert pv_engine._lat == 52.52
        assert pv_engine._panel_azimuth == 180.0
    
    def test_set_pv_system(self, pv_engine):
        pv_engine.set_pv_system(15.0, azimuth=170.0, tilt=35.0)
        assert pv_engine._pv_peak == 15.0
        assert pv_engine._panel_azimuth == 170.0
    
    def test_set_efficiency(self, pv_engine):
        pv_engine.set_system_efficiency(0.9)
        assert pv_engine._system_efficiency == 0.9
    
    def test_generate_hourly_forecast(self, pv_engine):
        forecast = pv_engine.generate_hourly_forecast(hours=48)
        assert len(forecast) == 48
        assert isinstance(forecast[0], PVHourlyForecast)
    
    def test_night_hours_zero_pv(self, pv_engine):
        forecast = pv_engine.generate_hourly_forecast(hours=48)
        for point in forecast:
            if point.solar_elevation <= 0:
                assert point.pv_power_kw == 0
                assert point.pv_energy_wh == 0
    
    def test_daylight_hours_positive_pv(self, pv_engine):
        forecast = pv_engine.generate_hourly_forecast(hours=48)
        daylight_hours = [p for p in forecast if p.solar_elevation > 0]
        assert len(daylight_hours) > 0
        for point in daylight_hours:
            assert point.pv_power_kw >= 0
    
    def test_solar_position_valid(self, pv_engine):
        forecast = pv_engine.generate_hourly_forecast(hours=24)
        for point in forecast:
            assert -90 <= point.solar_elevation <= 90
            assert 0 <= point.solar_azimuth <= 360
    
    def test_cloud_cover_impact(self, pv_engine):
        # Clear sky
        weather_clear = [{"cloud_cover_pct": 0} for _ in range(48)]
        pv_engine.set_weather_data(weather_clear)
        forecast_clear = pv_engine.generate_hourly_forecast(hours=48)
        
        # Overcast
        weather_cloudy = [{"cloud_cover_pct": 100} for _ in range(48)]
        pv_engine.set_weather_data(weather_cloudy)
        forecast_cloudy = pv_engine.generate_hourly_forecast(hours=48)
        
        # Clear should produce more power
        total_clear = sum(p.pv_power_kw for p in forecast_clear)
        total_cloudy = sum(p.pv_power_kw for p in forecast_cloudy)
        assert total_clear > total_cloudy
    
    def test_weather_condition_assignment(self, pv_engine):
        weather = [
            {"cloud_cover_pct": 10, "precipitation_mm": 0},
            {"cloud_cover_pct": 50, "precipitation_mm": 0},
            {"cloud_cover_pct": 90, "precipitation_mm": 5},
        ] * 16
        pv_engine.set_weather_data(weather)
        forecast = pv_engine.generate_hourly_forecast(hours=48)
        
        conditions = set(p.weather_condition for p in forecast)
        assert len(conditions) > 1
    
    def test_daily_forecast(self, pv_engine):
        daily = pv_engine.generate_daily_forecast(days=7)
        assert len(daily) == 7
        assert isinstance(daily[0], PVDailyForecast)
        assert daily[0].total_energy_kwh >= 0
    
    def test_daily_sunrise_sunset(self, pv_engine):
        daily = pv_engine.generate_daily_forecast(days=1)
        day = daily[0]
        assert "T" in day.sunrise
        assert "T" in day.sunset
        assert day.daylight_hours > 0
    
    def test_summary_generation(self, pv_engine):
        forecast = pv_engine.generate_hourly_forecast(hours=48)
        summary = pv_engine.generate_summary(forecast)
        assert isinstance(summary, PVForecastSummary)
        assert summary.forecast_horizon_hours == 48
        assert summary.total_energy_kwh >= 0
        assert 0 <= summary.weather_impact_pct <= 100
    
    def test_dict_export(self, pv_engine):
        result = pv_engine.get_pv_forecast_as_dict(hours=48)
        assert "generated_at" in result
        assert "pv_system" in result
        assert "location" in result
        assert "summary" in result
        assert len(result["hourly_forecast"]) == 48


# ──────────────────────────────────────────────────────────────────────────
# LoadShiftingEngine Tests
# ──────────────────────────────────────────────────────────────────────────

class TestLoadShiftingEngine:
    """Tests for LoadShiftingEngine."""
    
    @pytest.fixture
    def shifting_engine(self):
        engine = LoadShiftingEngine()
        # Add test devices
        engine.add_device_from_profile("washer_1", "washer", "Waschmaschine")
        engine.add_device_from_profile("ev_1", "ev_charger", "EV-Ladestation")
        return engine
    
    def test_initialization(self, shifting_engine):
        assert len(shifting_engine._devices) == 2
    
    def test_add_device(self, shifting_engine):
        device = ShiftableDevice(
            device_id="dryer_1",
            device_type="dryer",
            name="Trockner",
            power_kw=2.5,
            energy_kwh=3.0,
            duration_hours=1.5,
            flexibility_hours=12,
            priority=3,
            min_start_hour=0,
            max_start_hour=23,
            must_complete_by=None,
            current_state="idle",
            cost_per_kwh=30.0,
        )
        shifting_engine.add_device(device)
        assert len(shifting_engine._devices) == 3
    
    def test_set_pv_forecast(self, shifting_engine):
        pv_forecast = [{"pv_power_kw": 2.0 + i * 0.5} for i in range(24)]
        shifting_engine.set_pv_forecast(pv_forecast)
        assert len(shifting_engine._pv_forecast) == 24
    
    def test_set_price_forecast(self, shifting_engine):
        price_forecast = [{"price_ct_kwh": 25.0 + (i % 10)} for i in range(24)]
        shifting_engine.set_price_forecast(price_forecast)
        assert len(shifting_engine._price_forecast) == 24
    
    def test_generate_recommendations(self, shifting_engine):
        # Set up forecasts - PV peak at noon, cheap prices at midday
        pv_forecast = [{"pv_power_kw": max(0, 5.0 - abs(12 - i) * 0.5)} for i in range(24)]
        price_forecast = [{"price_ct_kwh": 40.0 - abs(12 - i) * 1.5} for i in range(24)]  # Cheap at noon
        
        shifting_engine.set_pv_forecast(pv_forecast)
        shifting_engine.set_price_forecast(price_forecast)
        
        recommendations = shifting_engine.generate_recommendations()
        
        assert isinstance(recommendations, list)
        for rec in recommendations:
            assert isinstance(rec, LoadShiftRecommendation)
            assert rec.action in ["start_now", "delay", "advance", "schedule"]
            assert 0 <= rec.confidence <= 1
            # Savings can be negative if optimization suggests waiting
            # Just check the calculation is reasonable
            assert rec.cost_original > 0
            assert rec.cost_optimized > 0
    
    def test_recommendations_sorted_by_savings(self, shifting_engine):
        pv_forecast = [{"pv_power_kw": 2.0} for _ in range(24)]
        price_forecast = [{"price_ct_kwh": 30.0} for _ in range(24)]
        
        shifting_engine.set_pv_forecast(pv_forecast)
        shifting_engine.set_price_forecast(price_forecast)
        
        recommendations = shifting_engine.generate_recommendations()
        
        if len(recommendations) > 1:
            for i in range(len(recommendations) - 1):
                assert recommendations[i].savings_eur >= recommendations[i+1].savings_eur
    
    def test_optimization_windows(self, shifting_engine):
        pv_forecast = [{"pv_power_kw": max(0, 5.0 - abs(12 - i) * 0.5)} for i in range(24)]
        price_forecast = [{"price_ct_kwh": 25.0 + (i % 24 - 12)} for i in range(24)]
        
        shifting_engine.set_pv_forecast(pv_forecast)
        shifting_engine.set_price_forecast(price_forecast)
        
        windows = shifting_engine.generate_optimization_windows(hours_ahead=24)
        
        assert isinstance(windows, list)
        assert len(windows) <= 4  # Top 4 windows
        for window in windows:
            assert isinstance(window, OptimizationWindow)
            assert window.duration_hours > 0
            assert window.avg_price_ct_kwh > 0
    
    def test_summary_generation(self, shifting_engine):
        # Set up reasonable forecasts first
        pv_forecast = [{"pv_power_kw": max(0, 5.0 - abs(12 - i) * 0.5)} for i in range(24)]
        price_forecast = [{"price_ct_kwh": 40.0 - abs(12 - i) * 1.5} for i in range(24)]
        
        shifting_engine.set_pv_forecast(pv_forecast)
        shifting_engine.set_price_forecast(price_forecast)
        
        recommendations = shifting_engine.generate_recommendations()
        summary = shifting_engine.generate_summary(recommendations)
        
        assert isinstance(summary, LoadShiftSummary)
        assert summary.total_devices == 2
        assert summary.recommendations_count == len(recommendations)
        # Savings can be negative in edge cases, just check it's calculated
        assert isinstance(summary.total_potential_savings_eur, float)
    
    def test_dict_export(self, shifting_engine):
        result = shifting_engine.get_recommendations_as_dict()
        
        assert "generated_at" in result
        assert "summary" in result
        assert "recommendations" in result
        assert "optimization_windows" in result
        assert "devices" in result
    
    def test_simple_recommendation_text(self, shifting_engine):
        text = shifting_engine.get_simple_recommendation_text()
        assert isinstance(text, str)
        assert len(text) > 0
    
    def test_pv_utilization_calculation(self, shifting_engine):
        pv_forecast = [{"pv_power_kw": 5.0} for _ in range(24)]  # Constant PV
        shifting_engine.set_pv_forecast(pv_forecast)
        
        # Device needs 2 hours
        device = shifting_engine._devices[0]
        pv_util = shifting_engine._calculate_pv_utilization(
            start_hour=10,
            duration_hours=2,
            device_power_kw=device.power_kw,
        )
        
        assert 0 <= pv_util <= 1
    
    def test_device_states(self, shifting_engine):
        # Set one device to running
        shifting_engine._devices[0].current_state = "running"
        
        recommendations = shifting_engine.generate_recommendations()
        
        # Running device should not have recommendations
        device_ids = [r.device_id for r in recommendations]
        assert shifting_engine._devices[0].device_id not in device_ids
    
    def test_priority_handling(self, shifting_engine):
        # Add high priority device
        shifting_engine.add_device_from_profile(
            "heat_pump_1",
            "heat_pump",
            "Wärmepumpe",
            priority=5,
        )
        
        recommendations = shifting_engine.generate_recommendations()
        
        # All devices should be considered
        assert len(recommendations) >= 2


# ──────────────────────────────────────────────────────────────────────────
# Integration Tests
# ──────────────────────────────────────────────────────────────────────────

class TestIntegration:
    """Integration tests for combined energy forecasting."""
    
    def test_combined_forecast_workflow(self):
        """Test complete workflow: consumption + pv + load shifting."""
        # Initialize all engines
        consumption_engine = EnergyForecastEngine(latitude=52.52, longitude=13.405)
        pv_engine = PVPredictionEngine(latitude=52.52, longitude=13.405, pv_peak_kw=10.0)
        shifting_engine = LoadShiftingEngine()
        
        # Generate forecasts
        consumption = consumption_engine.generate_hourly_forecast(hours=48)
        pv = pv_engine.generate_hourly_forecast(hours=48)
        
        # Set up load shifting
        shifting_engine.set_pv_forecast([{"pv_power_kw": p.pv_power_kw} for p in pv])
        shifting_engine.add_device_from_profile("washer_1", "washer", "Waschmaschine")
        
        recommendations = shifting_engine.generate_recommendations()
        
        # Verify all components work together
        assert len(consumption) == 48
        assert len(pv) == 48
        assert len(recommendations) >= 1
    
    def test_weather_data_flow(self):
        """Test weather data flows through all engines."""
        weather_data = [
            {
                "temperature_c": 15.0 - i * 0.2,
                "cloud_cover_pct": 30 + i,
                "precipitation_mm": 0.5 if i % 5 == 0 else 0,
            }
            for i in range(48)
        ]
        
        # Consumption with weather
        consumption_engine = EnergyForecastEngine()
        consumption = consumption_engine.generate_hourly_forecast(
            hours=48,
            weather_data=weather_data,
        )
        
        # PV with weather
        pv_engine = PVPredictionEngine(pv_peak_kw=10.0)
        pv_weather = [
            {
                "timestamp": (datetime.now() + timedelta(hours=i)).isoformat(),
                **w,
            }
            for i, w in enumerate(weather_data)
        ]
        pv_engine.set_weather_data(pv_weather)
        pv = pv_engine.generate_hourly_forecast(hours=48)
        
        # Verify weather impacts both
        assert len(consumption) == 48
        assert len(pv) == 48
        # Weather data should influence PV output (some hours have non-zero power)
        assert any(h.pv_power_kw > 0 for h in pv)
        # Higher cloud cover should reduce actual vs clearsky irradiance
        daytime = [h for h in pv if h.solar_elevation > 10]
        if len(daytime) >= 2:
            avg_efficiency = sum(h.efficiency_factor for h in daytime) / len(daytime)
            assert avg_efficiency < 1.0  # clouds reduce efficiency below clearsky


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
