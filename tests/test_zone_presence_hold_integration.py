"""Zone Presence Hold Integration Tests — Slice 40.

Tests the integration between ZonePresenceHoldStore and PresenceModule.
Validates that hold states (FORCE_ON/FORCE_OFF) correctly override sensor-based detection.
"""
from __future__ import annotations

import pytest
from datetime import datetime, timezone, timedelta
from unittest.mock import patch, MagicMock

from copilot_core.core.zone_presence_hold import (
    ZonePresenceHoldStore,
    ZoneHoldState,
    get_zone_presence_hold_store,
)
from copilot_core.presence.zone_presence import (
    PresenceModule,
    PresenceConfig,
    PresenceState,
    PresenceSensor,
    PresenceSensorType,
)


class TestZonePresenceHoldIntegration:
    """Test hold state integration with presence detection."""
    
    @pytest.fixture(autouse=True)
    def reset_global_store(self):
        """Reset the global hold store before each test."""
        store = get_zone_presence_hold_store()
        store.clear()
        yield
        store.clear()
    
    @pytest.fixture
    def hold_store(self):
        """Get the global hold store."""
        return get_zone_presence_hold_store()
    
    @pytest.fixture
    def presence_module(self):
        """Fresh presence module for each test."""
        return PresenceModule()
    
    @pytest.fixture
    def zone_id(self):
        return "zone_living_room"
    
    @pytest.fixture
    def sensor_config(self, zone_id):
        return PresenceSensor(
            sensor_id="sensor_mmwave_001",
            zone_id=zone_id,
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="binary_sensor.living_room_mmwave",
            name="Living Room mmWave",
            enabled=True,
            priority=80,
            confidence=0.95,
        )
    
    def test_hold_store_integration_available(self):
        """Verify hold store integration is available."""
        store = get_zone_presence_hold_store()
        assert store is not None
        assert isinstance(store, ZonePresenceHoldStore)
    
    def test_presence_module_has_hold_integration_methods(self, presence_module):
        """Verify PresenceModule has hold integration methods."""
        assert hasattr(presence_module, "_get_effective_hold_state")
        assert hasattr(presence_module, "get_hold_state")
        assert hasattr(presence_module, "is_hold_enforced")
    
    def test_no_hold_returns_auto(self, presence_module, zone_id):
        """Test that zones without holds return AUTO state."""
        hold_state = presence_module._get_effective_hold_state(zone_id)
        assert hold_state == ZoneHoldState.AUTO
        assert presence_module.get_hold_state(zone_id) == "auto"
        assert not presence_module.is_hold_enforced(zone_id)
    
    def test_force_on_hold_overrides_presence_detection(
        self, presence_module, hold_store, zone_id, sensor_config
    ):
        """Test FORCE_ON hold overrides sensor logic to always return PRESENT."""
        # Set up hold
        hold_store.set_hold(zone_id, ZoneHoldState.FORCE_ON, reason="test_force_on")
        
        # Add sensor to module
        presence_module.add_sensor(sensor_config)
        presence_module.set_zone_config(
            zone_id,
            PresenceConfig(
                zone_id=zone_id,
                on_delay_seconds=0,
                off_delay_seconds=5,
            ),
        )
        
        # Verify hold state is detected
        hold_state = presence_module._get_effective_hold_state(zone_id)
        assert hold_state == ZoneHoldState.FORCE_ON
        assert presence_module.is_hold_enforced(zone_id)
        
        # Update sensor to NOT present (simulate no motion)
        presence_module.update_sensor_state(sensor_config.sensor_id, False)
        
        # Get zone presence - should be PRESENT due to FORCE_ON hold
        zone_state = presence_module.get_zone_presence(zone_id)
        assert zone_state is not None
        assert zone_state.state == PresenceState.PRESENT
        assert zone_state.confidence == 1.0
    
    def test_force_off_hold_overrides_presence_detection(
        self, presence_module, hold_store, zone_id, sensor_config
    ):
        """Test FORCE_OFF hold overrides sensor logic to always return ABSENT."""
        # Set up hold
        hold_store.set_hold(zone_id, ZoneHoldState.FORCE_OFF, reason="test_force_off")
        
        # Add sensor to module
        presence_module.add_sensor(sensor_config)
        presence_module.set_zone_config(
            zone_id,
            PresenceConfig(
                zone_id=zone_id,
                on_delay_seconds=0,
                off_delay_seconds=5,
            ),
        )
        
        # Verify hold state is detected
        hold_state = presence_module._get_effective_hold_state(zone_id)
        assert hold_state == ZoneHoldState.FORCE_OFF
        assert presence_module.is_hold_enforced(zone_id)
        
        # Update sensor to present (simulate motion detected)
        presence_module.update_sensor_state(sensor_config.sensor_id, True)
        
        # Get zone presence - should be ABSENT due to FORCE_OFF hold
        zone_state = presence_module.get_zone_presence(zone_id)
        assert zone_state is not None
        assert zone_state.state == PresenceState.ABSENT
    
    def test_auto_hold_allows_normal_sensor_logic(
        self, presence_module, hold_store, zone_id, sensor_config
    ):
        """Test AUTO hold allows normal sensor-based detection."""
        # Set up AUTO hold (or no hold)
        hold_store.set_hold(zone_id, ZoneHoldState.AUTO, reason="test_auto")
        
        # Add sensor to module
        presence_module.add_sensor(sensor_config)
        presence_module.set_zone_config(
            zone_id,
            PresenceConfig(
                zone_id=zone_id,
                on_delay_seconds=0,
                off_delay_seconds=5,
            ),
        )
        
        # Verify hold state is AUTO
        hold_state = presence_module._get_effective_hold_state(zone_id)
        assert hold_state == ZoneHoldState.AUTO
        assert not presence_module.is_hold_enforced(zone_id)
        
        # Update sensor to present
        presence_module.update_sensor_state(sensor_config.sensor_id, True)
        
        # Get zone presence - should follow sensor logic
        zone_state = presence_module.get_zone_presence(zone_id)
        assert zone_state is not None
        assert zone_state.state == PresenceState.PRESENT
        
        # Update sensor to absent
        presence_module.update_sensor_state(sensor_config.sensor_id, False)
        
        # Should transition to absent (after off-delay)
        zone_state = presence_module.get_zone_presence(zone_id)
        assert zone_state.state in (PresenceState.ABSENT, PresenceState.UNCERTAIN)
    
    def test_hold_state_changes_propagate_to_presence(
        self, presence_module, hold_store, zone_id, sensor_config
    ):
        """Test that changing hold state immediately affects presence detection."""
        # Add sensor and set config
        presence_module.add_sensor(sensor_config)
        presence_module.set_zone_config(
            zone_id,
            PresenceConfig(zone_id=zone_id, off_delay_seconds=5),
        )
        
        # Start with sensor present
        presence_module.update_sensor_state(sensor_config.sensor_id, True)
        
        # Verify initial state is PRESENT (sensor-based)
        zone_state = presence_module.get_zone_presence(zone_id)
        assert zone_state.state == PresenceState.PRESENT
        
        # Set FORCE_OFF hold
        hold_store.set_hold(zone_id, ZoneHoldState.FORCE_OFF, reason="test_change")
        
        # Verify state changes to ABSENT due to hold
        zone_state = presence_module.get_zone_presence(zone_id)
        assert zone_state.state == PresenceState.ABSENT
        
        # Change to FORCE_ON hold
        hold_store.set_hold(zone_id, ZoneHoldState.FORCE_ON, reason="test_change_on")
        
        # Verify state changes to PRESENT due to hold
        zone_state = presence_module.get_zone_presence(zone_id)
        assert zone_state.state == PresenceState.PRESENT
        
        # Release hold (back to AUTO)
        hold_store.release_hold(zone_id, reason="test_release")
        
        # Should return to sensor-based logic (sensor is still present)
        zone_state = presence_module.get_zone_presence(zone_id)
        assert zone_state.state == PresenceState.PRESENT
    
    def test_hold_expiration_resumes_sensor_logic(
        self, presence_module, hold_store, zone_id, sensor_config
    ):
        """Test that expired holds resume normal sensor-based detection."""
        # Set up hold with short expiration
        hold_store.set_hold(
            zone_id,
            ZoneHoldState.FORCE_OFF,
            reason="test_expiring",
            duration_seconds=1,  # 1 second expiration
        )
        
        # Add sensor
        presence_module.add_sensor(sensor_config)
        presence_module.set_zone_config(
            zone_id,
            PresenceConfig(zone_id=zone_id),
        )
        
        # Verify hold is active
        hold_state = presence_module._get_effective_hold_state(zone_id)
        assert hold_state == ZoneHoldState.FORCE_OFF
        
        # Wait for expiration
        import time
        time.sleep(1.1)
        
        # Hold should now be expired, falling back to AUTO
        hold_state = presence_module._get_effective_hold_state(zone_id)
        assert hold_state == ZoneHoldState.AUTO
        assert not presence_module.is_hold_enforced(zone_id)
    
    def test_multiple_zones_independent_holds(
        self, presence_module, hold_store
    ):
        """Test that holds work independently across multiple zones."""
        zone_a = "zone_living"
        zone_b = "zone_bedroom"
        
        sensor_a = PresenceSensor(
            sensor_id="sensor_a",
            zone_id=zone_a,
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="binary_sensor.living_mmwave",
            name="Living Sensor",
        )
        
        sensor_b = PresenceSensor(
            sensor_id="sensor_b",
            zone_id=zone_b,
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="binary_sensor.bedroom_mmwave",
            name="Bedroom Sensor",
        )
        
        # Add sensors
        presence_module.add_sensor(sensor_a)
        presence_module.add_sensor(sensor_b)
        
        # Set different holds for each zone
        hold_store.set_hold(zone_a, ZoneHoldState.FORCE_ON, reason="test_a")
        hold_store.set_hold(zone_b, ZoneHoldState.FORCE_OFF, reason="test_b")
        
        # Verify independent hold states
        assert presence_module._get_effective_hold_state(zone_a) == ZoneHoldState.FORCE_ON
        assert presence_module._get_effective_hold_state(zone_b) == ZoneHoldState.FORCE_OFF
        
        # Verify presence states follow holds
        zone_a_state = presence_module.get_zone_presence(zone_a)
        zone_b_state = presence_module.get_zone_presence(zone_b)
        
        assert zone_a_state.state == PresenceState.PRESENT
        assert zone_b_state.state == PresenceState.ABSENT
    
    def test_hold_state_human_readable_format(self, presence_module, hold_store, zone_id):
        """Test that get_hold_state returns human-readable strings."""
        # No hold
        assert presence_module.get_hold_state(zone_id) == "auto"
        
        # FORCE_ON
        hold_store.set_hold(zone_id, ZoneHoldState.FORCE_ON)
        assert presence_module.get_hold_state(zone_id) == "force_on"
        
        # FORCE_OFF
        hold_store.set_hold(zone_id, ZoneHoldState.FORCE_OFF)
        assert presence_module.get_hold_state(zone_id) == "force_off"
        
        # Back to AUTO
        hold_store.release_hold(zone_id)
        assert presence_module.get_hold_state(zone_id) == "auto"
    
    def test_graceful_degradation_on_store_failure(
        self, presence_module, zone_id
    ):
        """Test that presence module gracefully handles hold store failures."""
        # Mock store to raise exception
        with patch(
            "copilot_core.presence.zone_presence.get_zone_presence_hold_store",
            side_effect=Exception("Store unavailable"),
        ):
            # Should fall back to AUTO without crashing
            hold_state = presence_module._get_effective_hold_state(zone_id)
            assert hold_state == ZoneHoldState.AUTO
            assert not presence_module.is_hold_enforced(zone_id)


class TestZonePresenceHoldEndToEnd:
    """End-to-end tests for hold + presence integration."""
    
    def test_full_lifecycle_hold_presence_interaction(self):
        """Test complete lifecycle: no hold → force_on → force_off → release."""
        # Use global store
        hold_store = get_zone_presence_hold_store()
        hold_store.clear()
        
        presence = PresenceModule()
        
        zone_id = "zone_test"
        sensor = PresenceSensor(
            sensor_id="sensor_test",
            zone_id=zone_id,
            sensor_type=PresenceSensorType.PIR,
            entity_id="binary_sensor.test_pir",
            name="Test PIR",
        )
        
        # Setup
        presence.add_sensor(sensor)
        presence.set_zone_config(
            zone_id,
            PresenceConfig(zone_id=zone_id, off_delay_seconds=10),
        )
        
        # Phase 1: No hold, sensor absent → ABSENT
        presence.update_sensor_state(sensor.sensor_id, False)
        state = presence.get_zone_presence(zone_id)
        assert state.state == PresenceState.ABSENT
        
        # Phase 2: Set FORCE_ON → PRESENT (overrides sensor)
        hold_store.set_hold(zone_id, ZoneHoldState.FORCE_ON, reason="e2e_test")
        state = presence.get_zone_presence(zone_id)
        assert state.state == PresenceState.PRESENT
        assert presence.get_hold_state(zone_id) == "force_on"
        
        # Phase 3: Set FORCE_OFF → ABSENT (overrides sensor)
        hold_store.set_hold(zone_id, ZoneHoldState.FORCE_OFF, reason="e2e_test")
        state = presence.get_zone_presence(zone_id)
        assert state.state == PresenceState.ABSENT
        assert presence.get_hold_state(zone_id) == "force_off"
        
        # Phase 4: Release hold → back to sensor logic (still absent)
        hold_store.release_hold(zone_id, reason="e2e_release")
        state = presence.get_zone_presence(zone_id)
        assert state.state == PresenceState.ABSENT
        assert presence.get_hold_state(zone_id) == "auto"
        
        # Phase 5: Sensor goes present → PRESENT (normal logic resumes)
        presence.update_sensor_state(sensor.sensor_id, True)
        state = presence.get_zone_presence(zone_id)
        assert state.state == PresenceState.PRESENT
        
        # Cleanup
        hold_store.clear()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
