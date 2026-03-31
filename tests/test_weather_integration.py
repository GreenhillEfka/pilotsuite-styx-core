"""Tests for Weather Integration Engine — Slice 20."""
import pytest
from copilot_core.weather.integration_engine import (
    WeatherIntegrationEngine,
    WeatherCondition,
    WeatherAlertType,
    create_weather_integration_engine,
)
from datetime import datetime, timezone, timedelta


class TestWeatherIntegrationEngine:
    """Test weather integration engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_weather_integration_engine()
        assert engine is not None
    
    def test_register_weather_source(self):
        """Test weather source registration."""
        engine = WeatherIntegrationEngine()
        
        source_id = engine.register_weather_source(
            source_id="weather_home",
            name="Home Weather",
            source_type="ha",
            entity_id="weather.home",
        )
        
        assert source_id == "weather_home"
        assert source_id in engine._sources
        assert engine._sources[source_id]["name"] == "Home Weather"
    
    def test_update_current_weather(self):
        """Test updating current weather."""
        engine = WeatherIntegrationEngine()
        engine.register_weather_source("weather_test", "Test", "ha")
        
        weather = engine.update_current_weather("weather_test", {
            "temperature": 22.5,
            "humidity": 65.0,
            "pressure": 1013.25,
            "wind_speed": 15.0,
            "condition": "clear",
        })
        
        assert weather.temperature == 22.5
        assert weather.humidity == 65.0
        assert weather.condition == WeatherCondition.CLEAR
    
    def test_parse_condition_clear(self):
        """Test condition parsing - clear."""
        engine = WeatherIntegrationEngine()
        
        assert engine._parse_condition("clear") == WeatherCondition.CLEAR
        assert engine._parse_condition("sunny") == WeatherCondition.CLEAR
        assert engine._parse_condition("sonnig") == WeatherCondition.CLEAR
    
    def test_parse_condition_rain(self):
        """Test condition parsing - rain."""
        engine = WeatherIntegrationEngine()
        
        assert engine._parse_condition("rain") == WeatherCondition.RAINY
        assert engine._parse_condition("regen") == WeatherCondition.RAINY
        assert engine._parse_condition("rainy") == WeatherCondition.RAINY
    
    def test_parse_condition_storm(self):
        """Test condition parsing - storm."""
        engine = WeatherIntegrationEngine()
        
        assert engine._parse_condition("storm") == WeatherCondition.STORM
        assert engine._parse_condition("gewitter") == WeatherCondition.STORM
        assert engine._parse_condition("thunderstorm") == WeatherCondition.STORM
    
    def test_parse_condition_unknown(self):
        """Test condition parsing - unknown."""
        engine = WeatherIntegrationEngine()
        
        assert engine._parse_condition("unknown_condition") == WeatherCondition.UNKNOWN
    
    def test_import_forecast(self):
        """Test forecast import."""
        engine = WeatherIntegrationEngine()
        engine.register_weather_source("weather_test", "Test", "ha")
        
        now = datetime.now(timezone.utc)
        
        forecasts = [
            {
                "start": (now + timedelta(days=1)).isoformat(),
                "end": (now + timedelta(days=1, hours=23, minutes=59)).isoformat(),
                "temperature_min": 10.0,
                "temperature_max": 20.0,
                "condition": "cloudy",
                "precipitation_probability": 30.0,
            },
            {
                "start": (now + timedelta(days=2)).isoformat(),
                "end": (now + timedelta(days=2, hours=23, minutes=59)).isoformat(),
                "temperature_min": 12.0,
                "temperature_max": 22.0,
                "condition": "clear",
                "precipitation_probability": 10.0,
            },
        ]
        
        imported = engine.import_forecast("weather_test", forecasts)
        
        assert imported == 2
        assert len(engine._forecasts["weather_test"]) == 2
    
    def test_get_current_weather(self):
        """Test getting current weather."""
        engine = WeatherIntegrationEngine()
        engine.register_weather_source("weather_test", "Test", "ha")
        
        engine.update_current_weather("weather_test", {
            "temperature": 18.5,
            "humidity": 70.0,
            "condition": "partly cloudy",
        })
        
        weather = engine.get_current_weather("weather_test")
        
        assert weather is not None
        assert weather["temperature"] == 18.5
        assert weather["condition"] == "partly_cloudy"
    
    def test_get_forecast(self):
        """Test getting forecast."""
        engine = WeatherIntegrationEngine()
        engine.register_weather_source("weather_test", "Test", "ha")
        
        now = datetime.now(timezone.utc)
        
        forecasts = [
            {"start": (now + timedelta(days=1)).isoformat(), "end": (now + timedelta(days=2)).isoformat(), "temperature_min": 10.0, "temperature_max": 20.0, "condition": "clear"},
            {"start": (now + timedelta(days=2)).isoformat(), "end": (now + timedelta(days=3)).isoformat(), "temperature_min": 11.0, "temperature_max": 21.0, "condition": "cloudy"},
            {"start": (now + timedelta(days=3)).isoformat(), "end": (now + timedelta(days=4)).isoformat(), "temperature_min": 12.0, "temperature_max": 22.0, "condition": "rain"},
        ]
        
        engine.import_forecast("weather_test", forecasts)
        
        # Get 2-day forecast
        forecast = engine.get_forecast(days_ahead=2)
        
        assert len(forecast) >= 1
    
    def test_create_weather_alert(self):
        """Test creating weather alert."""
        engine = WeatherIntegrationEngine()
        
        now = datetime.now(timezone.utc)
        
        alert_id = engine.create_alert(
            alert_type=WeatherAlertType.STORM_WARNING,
            severity="severe",
            title="Storm Warning",
            description="Severe storm expected",
            start=now,
            end=now + timedelta(hours=6),
        )
        
        assert alert_id is not None
        assert alert_id in engine._alerts
        assert engine._alerts[alert_id].alert_type == WeatherAlertType.STORM_WARNING
    
    def test_get_alerts(self):
        """Test getting alerts."""
        engine = WeatherIntegrationEngine()
        
        now = datetime.now(timezone.utc)
        
        # Create alerts
        engine.create_alert(WeatherAlertType.STORM_WARNING, "severe", "Storm", "Description", now, now + timedelta(hours=6))
        engine.create_alert(WeatherAlertType.WIND_WARNING, "minor", "Wind", "Description", now, now + timedelta(hours=3))
        
        alerts = engine.get_alerts(active_only=True)
        
        assert len(alerts) >= 1
        
        # Should be sorted by severity (severe first)
        if len(alerts) >= 2:
            assert alerts[0]["severity"] == "severe"
    
    def test_acknowledge_alert(self):
        """Test acknowledging alert."""
        engine = WeatherIntegrationEngine()
        
        now = datetime.now(timezone.utc)
        alert_id = engine.create_alert(WeatherAlertType.FOG_WARNING, "moderate", "Fog", "Description", now)
        
        # Acknowledge
        result = engine.acknowledge_alert(alert_id)
        
        assert result is True
        assert engine._alerts[alert_id].acknowledged is True
    
    def test_create_temperature_automation(self):
        """Test creating temperature-based automation."""
        engine = WeatherIntegrationEngine()
        
        auto_id = engine.create_automation(
            actions=[{"domain": "climate", "service": "turn_on"}],
            temperature_threshold=25.0,
            temperature_operator="above",
        )
        
        assert auto_id is not None
        assert auto_id in engine._automations
        assert engine._automations[auto_id].temperature_threshold == 25.0
    
    def test_create_condition_automation(self):
        """Test creating condition-based automation."""
        engine = WeatherIntegrationEngine()
        
        auto_id = engine.create_automation(
            actions=[{"domain": "cover", "service": "close"}],
            condition_trigger=WeatherCondition.RAINY,
        )
        
        assert auto_id is not None
        assert engine._automations[auto_id].condition_trigger == WeatherCondition.RAINY
    
    def test_create_alert_automation(self):
        """Test creating alert-based automation."""
        engine = WeatherIntegrationEngine()
        
        auto_id = engine.create_automation(
            actions=[{"domain": "notify", "service": "send"}],
            alert_trigger=WeatherAlertType.STORM_WARNING,
        )
        
        assert auto_id is not None
        assert engine._automations[auto_id].alert_trigger == WeatherAlertType.STORM_WARNING
    
    def test_weather_automation_trigger(self):
        """Test weather automation triggering."""
        engine = WeatherIntegrationEngine()
        
        # Create automation for rainy weather
        engine.create_automation(
            actions=[{"domain": "cover", "service": "close"}],
            condition_trigger=WeatherCondition.RAINY,
        )
        
        engine.register_weather_source("weather_test", "Test", "ha")
        
        # Update with rainy weather
        engine.update_current_weather("weather_test", {
            "temperature": 15.0,
            "condition": "rain",
        })
        
        # Automation should have been triggered
        for auto in engine._automations.values():
            if auto.condition_trigger == WeatherCondition.RAINY:
                assert auto.last_triggered is not None
    
    def test_temperature_automation_trigger_above(self):
        """Test temperature automation trigger (above threshold)."""
        engine = WeatherIntegrationEngine()
        
        # Create automation for high temperature
        engine.create_automation(
            actions=[{"domain": "climate", "service": "turn_on"}],
            temperature_threshold=30.0,
            temperature_operator="above",
        )
        
        engine.register_weather_source("weather_test", "Test", "ha")
        
        # Update with hot weather
        engine.update_current_weather("weather_test", {
            "temperature": 35.0,
            "condition": "clear",
        })
        
        # Automation should have been triggered
        for auto in engine._automations.values():
            if auto.temperature_threshold == 30.0:
                assert auto.last_triggered is not None
    
    def test_temperature_automation_no_trigger_below(self):
        """Test temperature automation doesn't trigger below threshold."""
        engine = WeatherIntegrationEngine()
        
        # Create automation for high temperature
        engine.create_automation(
            actions=[{"domain": "climate", "service": "turn_on"}],
            temperature_threshold=30.0,
            temperature_operator="above",
        )
        
        engine.register_weather_source("weather_test", "Test", "ha")
        
        # Update with normal weather
        engine.update_current_weather("weather_test", {
            "temperature": 20.0,
            "condition": "clear",
        })
        
        # Automation should NOT have been triggered
        for auto in engine._automations.values():
            if auto.temperature_threshold == 30.0:
                assert auto.last_triggered is None
    
    def test_get_weather_summary(self):
        """Test weather summary."""
        engine = WeatherIntegrationEngine()
        
        # Register sources
        engine.register_weather_source("src_1", "Source 1", "ha")
        engine.register_weather_source("src_2", "Source 2", "openweathermap")
        
        # Create automation
        engine.create_automation(actions=[])
        
        summary = engine.get_weather_summary()
        
        assert summary["total_sources"] == 2
        assert summary["active_automations"] == 1
    
    def test_weather_data_to_dict(self):
        """Test weather data serialization."""
        from copilot_core.weather.integration_engine import WeatherData
        
        now = datetime.now(timezone.utc)
        
        weather = WeatherData(
            source_id="test_source",
            temperature=22.5,
            humidity=65.0,
            pressure=1013.25,
            wind_speed=10.0,
            condition=WeatherCondition.CLEAR,
        )
        
        d = weather.to_dict()
        
        assert d["source_id"] == "test_source"
        assert d["temperature"] == 22.5
        assert d["humidity"] == 65.0
        assert d["condition"] == "clear"
    
    def test_forecast_to_dict(self):
        """Test forecast serialization."""
        from copilot_core.weather.integration_engine import WeatherForecast
        
        now = datetime.now(timezone.utc)
        
        forecast = WeatherForecast(
            forecast_id="fc_test",
            source_id="test_source",
            start=now,
            end=now + timedelta(hours=24),
            temperature_min=10.0,
            temperature_max=20.0,
            condition=WeatherCondition.CLOUDY,
            precipitation_probability=30.0,
        )
        
        d = forecast.to_dict()
        
        assert d["forecast_id"] == "fc_test"
        assert d["temperature_min"] == 10.0
        assert d["temperature_max"] == 20.0
        assert d["condition"] == "cloudy"
        assert "start" in d
        assert "end" in d
    
    def test_alert_to_dict(self):
        """Test alert serialization."""
        from copilot_core.weather.integration_engine import WeatherAlert
        
        now = datetime.now(timezone.utc)
        
        alert = WeatherAlert(
            alert_id="alert_test",
            alert_type=WeatherAlertType.STORM_WARNING,
            severity="severe",
            title="Storm",
            description="Storm warning",
            start=now,
            end=now + timedelta(hours=6),
        )
        
        d = alert.to_dict()
        
        assert d["alert_id"] == "alert_test"
        assert d["alert_type"] == "storm_warning"
        assert d["severity"] == "severe"
        assert d["title"] == "Storm"
        assert "start" in d
        assert "end" in d
    
    def test_automation_to_dict(self):
        """Test automation serialization."""
        from copilot_core.weather.integration_engine import WeatherAutomation
        
        auto = WeatherAutomation(
            automation_id="auto_test",
            condition_trigger=WeatherCondition.RAINY,
            temperature_threshold=None,
            temperature_operator=None,
            alert_trigger=None,
            actions=[{"domain": "cover", "service": "close"}],
        )
        
        d = auto.to_dict()
        
        assert d["automation_id"] == "auto_test"
        assert d["condition_trigger"] == "rainy"
        assert d["actions"] == [{"domain": "cover", "service": "close"}]
    
    def test_forecasts_sorted_by_start(self):
        """Test that forecasts are sorted by start time."""
        engine = WeatherIntegrationEngine()
        engine.register_weather_source("weather_test", "Test", "ha")
        
        now = datetime.now(timezone.utc)
        
        # Import in random order
        forecasts = [
            {"start": (now + timedelta(days=3)).isoformat(), "end": (now + timedelta(days=4)).isoformat(), "temperature_min": 12.0, "temperature_max": 22.0, "condition": "clear"},
            {"start": (now + timedelta(days=1)).isoformat(), "end": (now + timedelta(days=2)).isoformat(), "temperature_min": 10.0, "temperature_max": 20.0, "condition": "rain"},
            {"start": (now + timedelta(days=2)).isoformat(), "end": (now + timedelta(days=3)).isoformat(), "temperature_min": 11.0, "temperature_max": 21.0, "condition": "cloudy"},
        ]
        
        engine.import_forecast("weather_test", forecasts)
        
        # Get and verify order
        result = engine.get_forecast(days_ahead=7)
        
        assert result[0]["temperature_min"] == 10.0  # Day 1
        assert result[1]["temperature_min"] == 11.0  # Day 2
        assert result[2]["temperature_min"] == 12.0  # Day 3
