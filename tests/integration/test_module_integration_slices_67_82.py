"""Slice 83 — Module Integration Tests (v15.2.93).

Integration tests for Slices 67-82 modules:
- Presence Intelligence (Slice 70, 75)
- Light Intelligence (Slice 71, 76)
- TimeOfDay Intelligence (Slice 72, 77)
- Climate/HVAC Module (Slice 80)
- Humidity Module (Slice 81)
- Energy Module (Slice 82)
- Rules Engine (Slice 73, 78)

Tests module-to-module communication, event propagation, and cross-module state consistency.
"""

import pytest
import pytest_asyncio
from unittest.mock import Mock, MagicMock, patch, AsyncMock
from typing import Dict, List, Any, Optional
import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timedelta


# ── Test Fixtures ───────────────────────────────────────────────────────

@pytest.fixture
def mock_event_bus():
    """Mock event bus for inter-module communication."""
    bus = MagicMock()
    bus.publish = MagicMock()
    bus.subscribe = MagicMock()
    bus.emit = MagicMock()
    return bus


@pytest.fixture
def mock_zone_registry():
    """Mock zone registry."""
    registry = MagicMock()
    registry.get_zone = MagicMock(return_value={
        "id": "wohnzimmer",
        "name": "Wohnzimmer",
        "area_id": "area_wohnzimmer",
        "floor_id": "floor_1",
        "entities": {
            "presence": ["binary_sensor.wohnzimmer_motion"],
            "light": ["light.wohnzimmer_haupt", "light.wohnzimmer_stehlampe"],
            "climate": ["climate.wohnzimmer_thermostat"],
            "humidity": ["sensor.wohnzimmer_humidity"],
            "energy": ["sensor.wohnzimmer_power"],
        }
    })
    registry.list_zones = MagicMock(return_value=["wohnzimmer", "kuche", "bad", "schlafzimmer"])
    return registry


# ── Slice 70/75: Presence Intelligence Integration ─────────────────────

class TestPresenceIntegration:
    """Test Presence module integration with other modules."""

    def test_presence_triggers_light_automation(self, mock_event_bus, mock_zone_registry):
        """Presence detection should trigger light automation."""
        from copilot_core.presence.zone_presence import ZonePresenceEngine
        
        engine = ZonePresenceEngine(
            event_bus=mock_event_bus,
            zone_registry=mock_zone_registry
        )
        
        # Simulate person entered
        engine.on_person_entered("wohnzimmer", "person_andreas")
        
        # Verify light automation was triggered
        mock_event_bus.publish.assert_called()
        calls = mock_event_bus.publish.call_args_list
        assert any("light_automation" in str(call) for call in calls)

    def test_presence_updates_zone_state(self, mock_event_bus, mock_zone_registry):
        """Presence changes should update zone state."""
        from copilot_core.presence.zone_presence import ZonePresenceEngine
        
        engine = ZonePresenceEngine(
            event_bus=mock_event_bus,
            zone_registry=mock_zone_registry
        )
        
        engine.on_person_entered("wohnzimmer", "person_andreas")
        
        # Verify zone state updated
        mock_event_bus.emit.assert_called()
        calls = mock_event_bus.emit.call_args_list
        assert any("zone_state_updated" in str(call) for call in calls)

    def test_presence_departure_triggers_cleanup(self, mock_event_bus, mock_zone_registry):
        """Last person departure should trigger cleanup automation."""
        from copilot_core.presence.zone_presence import ZonePresenceEngine
        
        engine = ZonePresenceEngine(
            event_bus=mock_event_bus,
            zone_registry=mock_zone_registry
        )
        
        # First person enters
        engine.on_person_entered("wohnzimmer", "person_andreas")
        mock_event_bus.reset_mock()
        
        # Last person leaves
        engine.on_person_left("wohnzimmer", "person_andreas")
        
        # Verify cleanup triggered
        mock_event_bus.publish.assert_called()
        calls = mock_event_bus.publish.call_args_list
        assert any("cleanup" in str(call).lower() for call in calls)


# ── Slice 71/76: Light Intelligence Integration ────────────────────────

class TestLightIntegration:
    """Test Light module integration with other modules."""

    def test_light_respects_timeofday(self, mock_event_bus, mock_zone_registry):
        """Light scenes should respect time of day."""
        from copilot_core.light.zone_light import ZoneLightEngine
        
        engine = ZoneLightEngine(
            event_bus=mock_event_bus,
            zone_registry=mock_zone_registry
        )
        
        # Set time to evening
        engine.on_time_changed("evening")
        
        # Activate light scene
        engine.activate_scene("wohnzimmer", "relax")
        
        # Verify evening-appropriate brightness
        mock_event_bus.publish.assert_called()
        calls = mock_event_bus.publish.call_args_list
        # Should have lower brightness in evening
        assert any("brightness" in str(call) for call in calls)

    def test_light_follows_presence(self, mock_event_bus, mock_zone_registry):
        """Lights should follow presence detection."""
        from copilot_core.light.zone_light import ZoneLightEngine
        
        engine = ZoneLightEngine(
            event_bus=mock_event_bus,
            zone_registry=mock_zone_registry
        )
        
        # Presence detected
        engine.on_presence_detected("wohnzimmer")
        
        # Verify lights turned on
        mock_event_bus.publish.assert_called()
        calls = mock_event_bus.publish.call_args_list
        assert any("turn_on" in str(call) for call in calls)

    def test_light_energy_optimization(self, mock_event_bus, mock_zone_registry):
        """Light should optimize for energy efficiency."""
        from copilot_core.light.zone_light import ZoneLightEngine
        
        engine = ZoneLightEngine(
            event_bus=mock_event_bus,
            zone_registry=mock_zone_registry,
            enable_energy_optimization=True
        )
        
        # Activate with daylight available
        engine.on_daylight_available("wohnzimmer", lux_level=500)
        
        # Verify lights dimmed or off
        mock_event_bus.publish.assert_called()
        calls = mock_event_bus.publish.call_args_list
        assert any("dim" in str(call).lower() or "off" in str(call).lower() for call in calls)


# ── Slice 72/77: TimeOfDay Integration ─────────────────────────────────

class TestTimeOfDayIntegration:
    """Test TimeOfDay module integration."""

    def test_timeofday_triggers_mood_transition(self, mock_event_bus, mock_zone_registry):
        """Time changes should trigger mood transitions."""
        from copilot_core.timeofday.zone_time import TimeOfDayEngine
        
        engine = TimeOfDayEngine(
            event_bus=mock_event_bus,
            zone_registry=mock_zone_registry
        )
        
        # Transition to evening
        engine.on_time_transition("day", "evening")
        
        # Verify mood transition triggered
        mock_event_bus.publish.assert_called()
        calls = mock_event_bus.publish.call_args_list
        assert any("mood" in str(call).lower() for call in calls)

    def test_timeofday_updates_all_zones(self, mock_event_bus, mock_zone_registry):
        """Time changes should update all zones."""
        from copilot_core.timeofday.zone_time import TimeOfDayEngine
        
        engine = TimeOfDayEngine(
            event_bus=mock_event_bus,
            zone_registry=mock_zone_registry
        )
        
        engine.on_time_transition("day", "evening")
        
        # Verify all zones updated
        zones = mock_zone_registry.list_zones()
        for zone_id in zones:
            mock_zone_registry.get_zone.assert_called_with(zone_id)


# ── Slice 80: Climate/HVAC Integration ─────────────────────────────────

class TestClimateIntegration:
    """Test Climate module integration."""

    def test_climate_respects_presence(self, mock_event_bus, mock_zone_registry):
        """Climate should adjust based on presence."""
        from copilot_core.climate.climate import ClimateEngine
        
        engine = ClimateEngine(
            event_bus=mock_event_bus,
            zone_registry=mock_zone_registry
        )
        
        # No presence
        engine.on_zone_vacant("wohnzimmer")
        
        # Verify eco mode activated
        mock_event_bus.publish.assert_called()
        calls = mock_event_bus.publish.call_args_list
        assert any("eco" in str(call).lower() or "energy_save" in str(call).lower() for call in calls)

    def test_climate_preheating_on_schedule(self, mock_event_bus, mock_zone_registry):
        """Climate should preheat based on schedule."""
        from copilot_core.climate.climate import ClimateEngine
        
        engine = ClimateEngine(
            event_bus=mock_event_bus,
            zone_registry=mock_zone_registry
        )
        
        # Schedule event: home at 17:00
        engine.on_schedule_event("wohnzimmer", "home", "17:00")
        
        # Verify preheating started
        mock_event_bus.publish.assert_called()
        calls = mock_event_bus.publish.call_args_list
        assert any("preheat" in str(call).lower() or "target_temp" in str(call) for call in calls)


# ── Slice 81: Humidity Integration ─────────────────────────────────────

class TestHumidityIntegration:
    """Test Humidity module integration."""

    def test_humidity_triggers_ventilation(self, mock_event_bus, mock_zone_registry):
        """High humidity should trigger ventilation."""
        from copilot_core.humidity.humidity import HumidityEngine
        
        engine = HumidityEngine(
            event_bus=mock_event_bus,
            zone_registry=mock_zone_registry
        )
        
        # High humidity detected
        engine.on_humidity_high("bad", humidity_percent=75)
        
        # Verify ventilation triggered
        mock_event_bus.publish.assert_called()
        calls = mock_event_bus.publish.call_args_list
        assert any("ventilation" in str(call).lower() or "fan" in str(call).lower() for call in calls)

    def test_humidity_alert_on_mold_risk(self, mock_event_bus, mock_zone_registry):
        """Mold risk should trigger alert."""
        from copilot_core.humidity.humidity import HumidityEngine
        
        engine = HumidityEngine(
            event_bus=mock_event_bus,
            zone_registry=mock_zone_registry
        )
        
        # Critical humidity
        engine.on_humidity_critical("keller", humidity_percent=85, duration_hours=24)
        
        # Verify alert sent
        mock_event_bus.publish.assert_called()
        calls = mock_event_bus.publish.call_args_list
        assert any("alert" in str(call).lower() or "notification" in str(call).lower() for call in calls)


# ── Slice 82: Energy Integration ───────────────────────────────────────

class TestEnergyIntegration:
    """Test Energy module integration."""

    def test_energy_optimizes_climate(self, mock_event_bus, mock_zone_registry):
        """Energy module should optimize climate settings."""
        from copilot_core.energy.energy import EnergyEngine
        
        engine = EnergyEngine(
            event_bus=mock_event_bus,
            zone_registry=mock_zone_registry
        )
        
        # High energy price period
        engine.on_price_high("2026-03-31T18:00:00Z")
        
        # Verify climate optimization triggered
        mock_event_bus.publish.assert_called()
        calls = mock_event_bus.publish.call_args_list
        assert any("climate" in str(call).lower() and ("eco" in str(call).lower() or "reduce" in str(call).lower()) for call in calls)

    def test_energy_forecast_consumption(self, mock_event_bus, mock_zone_registry):
        """Energy module should forecast consumption."""
        from copilot_core.energy.energy import EnergyEngine
        
        engine = EnergyEngine(
            event_bus=mock_event_bus,
            zone_registry=mock_zone_registry
        )
        
        forecast = engine.get_daily_forecast("wohnzimmer")
        
        assert forecast is not None
        assert "kwh" in forecast or "consumption" in forecast or "forecast" in str(forecast).lower()


# ── Cross-Module Integration Tests ─────────────────────────────────────

class TestCrossModuleIntegration:
    """Test integration across multiple modules."""

    def test_good_morning_scenario(self, mock_event_bus, mock_zone_registry):
        """Test 'Good Morning' scenario across all modules."""
        from copilot_core.timeofday.zone_time import TimeOfDayEngine
        from copilot_core.presence.zone_presence import ZonePresenceEngine
        from copilot_core.light.zone_light import ZoneLightEngine
        from copilot_core.climate.climate import ClimateEngine
        
        time_engine = TimeOfDayEngine(event_bus=mock_event_bus, zone_registry=mock_zone_registry)
        presence_engine = ZonePresenceEngine(event_bus=mock_event_bus, zone_registry=mock_zone_registry)
        light_engine = ZoneLightEngine(event_bus=mock_event_bus, zone_registry=mock_zone_registry)
        climate_engine = ClimateEngine(event_bus=mock_event_bus, zone_registry=mock_zone_registry)
        
        # 7:00 AM: Time transition to morning
        time_engine.on_time_transition("night", "morning")
        
        # Person enters bathroom
        presence_engine.on_person_entered("bad", "person_andreas")
        
        # Verify coordinated response
        assert mock_event_bus.publish.call_count >= 3  # Time + Presence + Light/Climate
        
        # Verify lights on in bathroom
        light_calls = [c for c in mock_event_bus.publish.call_args_list if "light" in str(c).lower()]
        assert len(light_calls) > 0
        
        # Verify climate adjusted
        climate_calls = [c for c in mock_event_bus.publish.call_args_list if "climate" in str(c).lower()]
        assert len(climate_calls) > 0

    def test_leaving_home_scenario(self, mock_event_bus, mock_zone_registry):
        """Test 'Leaving Home' scenario across all modules."""
        from copilot_core.presence.zone_presence import ZonePresenceEngine
        from copilot_core.light.zone_light import ZoneLightEngine
        from copilot_core.climate.climate import ClimateEngine
        from copilot_core.energy.energy import EnergyEngine
        
        presence_engine = ZonePresenceEngine(event_bus=mock_event_bus, zone_registry=mock_zone_registry)
        light_engine = ZoneLightEngine(event_bus=mock_event_bus, zone_registry=mock_zone_registry)
        climate_engine = ClimateEngine(event_bus=mock_event_bus, zone_registry=mock_zone_registry)
        energy_engine = EnergyEngine(event_bus=mock_event_bus, zone_registry=mock_zone_registry)
        
        # All zones vacant
        for zone in ["wohnzimmer", "kuche", "bad", "schlafzimmer"]:
            presence_engine.on_person_left(zone, "person_andreas")
        
        # Verify all lights off
        light_calls = [c for c in mock_event_bus.publish.call_args_list if "off" in str(c).lower()]
        assert len(light_calls) > 0
        
        # Verify climate in eco mode
        climate_calls = [c for c in mock_event_bus.publish.call_args_list if "eco" in str(c).lower()]
        assert len(climate_calls) > 0
        
        # Verify energy optimization active
        energy_calls = [c for c in mock_event_bus.publish.call_args_list if "energy" in str(c).lower()]
        assert len(energy_calls) > 0

    def test_movie_night_scenario(self, mock_event_bus, mock_zone_registry):
        """Test 'Movie Night' scenario across modules."""
        from copilot_core.timeofday.zone_time import TimeOfDayEngine
        from copilot_core.light.zone_light import ZoneLightEngine
        from copilot_core.rules.rules import RulesEngine
        
        time_engine = TimeOfDayEngine(event_bus=mock_event_bus, zone_registry=mock_zone_registry)
        light_engine = ZoneLightEngine(event_bus=mock_event_bus, zone_registry=mock_zone_registry)
        rules_engine = RulesEngine(event_bus=mock_event_bus, zone_registry=mock_zone_registry)
        
        # Evening time
        time_engine.on_time_transition("day", "evening")
        
        # Movie mode activated
        rules_engine.activate_rule("movie_night", "wohnzimmer")
        
        # Verify dimmed lights
        light_calls = [c for c in mock_event_bus.publish.call_args_list if "dim" in str(c).lower() or "brightness" in str(c)]
        assert len(light_calls) > 0


# ── Event Propagation Tests ────────────────────────────────────────────

class TestEventPropagation:
    """Test event propagation across modules."""

    def test_zone_state_change_propagates(self, mock_event_bus, mock_zone_registry):
        """Zone state changes should propagate to all interested modules."""
        from copilot_core.hub.zone_automation import ZoneAutomationHub
        
        hub = ZoneAutomationHub(event_bus=mock_event_bus, zone_registry=mock_zone_registry)
        
        # Change zone state
        hub.update_zone_state("wohnzimmer", "occupied")
        
        # Verify all modules received event
        mock_event_bus.emit.assert_called()
        calls = mock_event_bus.emit.call_args_list
        assert len(calls) > 0

    def test_module_registry_discovers_all_modules(self, mock_zone_registry):
        """Module registry should discover all slice modules."""
        from copilot_core.registry.module_registry import ModuleRegistry
        
        registry = ModuleRegistry(zone_registry=mock_zone_registry)
        
        modules = registry.list_modules()
        
        # Verify all slice modules present
        module_names = [m["name"] for m in modules]
        assert "presence" in module_names
        assert "light" in module_names
        assert "climate" in module_names
        assert "humidity" in module_names
        assert "energy" in module_names
        assert "timeofday" in module_names
        assert "rules" in module_names


# ── Performance Tests ──────────────────────────────────────────────────

class TestModulePerformance:
    """Test module performance under load."""

    def test_presence_handles_rapid_events(self, mock_event_bus, mock_zone_registry):
        """Presence module should handle rapid event sequences."""
        from copilot_core.presence.zone_presence import ZonePresenceEngine
        
        engine = ZonePresenceEngine(event_bus=mock_event_bus, zone_registry=mock_zone_registry)
        
        # Simulate 100 rapid presence events
        start = time.time()
        for i in range(100):
            engine.on_person_entered("wohnzimmer", f"person_{i}")
        elapsed = time.time() - start
        
        # Should complete in under 1 second
        assert elapsed < 1.0, f"Too slow: {elapsed}s"

    def test_light_scene_switching_latency(self, mock_event_bus, mock_zone_registry):
        """Light scene switching should be low latency."""
        from copilot_core.light.zone_light import ZoneLightEngine
        
        engine = ZoneLightEngine(event_bus=mock_event_bus, zone_registry=mock_zone_registry)
        
        scenes = ["relax", "focus", "movie", "night", "morning"]
        
        start = time.time()
        for scene in scenes * 10:  # 50 scene switches
            engine.activate_scene("wohnzimmer", scene)
        elapsed = time.time() - start
        
        # Average < 50ms per switch
        assert elapsed / 50 < 0.05, f"Too slow: {elapsed/50*1000}ms per switch"


# ── Error Handling Tests ───────────────────────────────────────────────

class TestModuleErrorHandling:
    """Test module error handling and resilience."""

    def test_presence_handles_missing_zone(self, mock_event_bus, mock_zone_registry):
        """Presence module should handle unknown zones gracefully."""
        from copilot_core.presence.zone_presence import ZonePresenceEngine
        
        mock_zone_registry.get_zone.return_value = None
        engine = ZonePresenceEngine(event_bus=mock_event_bus, zone_registry=mock_zone_registry)
        
        # Should not raise
        engine.on_person_entered("unknown_zone", "person_andreas")
        
        # Verify error logged or handled
        mock_event_bus.publish.assert_called()
        calls = mock_event_bus.publish.call_args_list
        assert any("error" in str(call).lower() or "unknown" in str(call).lower() for call in calls)

    def test_module_config_validation(self, mock_zone_registry):
        """Modules should validate configuration on init."""
        from copilot_core.config.config_hub import ConfigHub
        
        config = ConfigHub(zone_registry=mock_zone_registry)
        
        # Invalid config should raise or return error
        with pytest.raises((ValueError, KeyError)) as exc_info:
            config.validate_module_config("presence", {"invalid": "config"})
        
        assert exc_info.value is not None


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
