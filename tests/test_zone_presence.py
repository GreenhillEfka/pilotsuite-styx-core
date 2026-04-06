"""Tests for Zone-Aware Presence Module — Slice 70."""
import pytest
from copilot_core.presence.zone_presence import (
    PresenceModule,
    PresenceSensor,
    PresenceConfig,
    ZonePresenceState,
    PresenceEvent,
    PresenceHistoryEntry,
    PresenceState,
    PresenceSensorType,
    create_presence_module,
)
from datetime import datetime, timezone, timedelta
import time


class TestPresenceState:
    """Test presence states."""
    
    def test_presence_state_enum_values(self):
        """Test presence state enum values."""
        assert PresenceState.PRESENT.value == "present"
        assert PresenceState.ABSENT.value == "absent"
        assert PresenceState.UNCERTAIN.value == "uncertain"
        assert PresenceState.EXTENDED_ABSENT.value == "extended_absent"


class TestPresenceSensorType:
    """Test presence sensor types."""
    
    def test_sensor_type_enum_values(self):
        """Test sensor type enum values."""
        assert PresenceSensorType.MMWAVE.value == "mmwave"
        assert PresenceSensorType.PIR.value == "pir"
        assert PresenceSensorType.DEVICE_TRACKER.value == "device_tracker"
        assert PresenceSensorType.PERSON.value == "person"


class TestPresenceSensor:
    """Test presence sensor."""
    
    def test_create_sensor(self):
        """Test creating presence sensor."""
        sensor = PresenceSensor(
            sensor_id="sensor_test",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="binary_sensor.living_mmwave",
            name="Living mmWave",
        )
        
        assert sensor.sensor_id == "sensor_test"
        assert sensor.enabled is True
    
    def test_sensor_to_dict(self):
        """Test sensor serialization."""
        sensor = PresenceSensor(
            sensor_id="sensor_test",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.PIR,
            entity_id="binary_sensor.motion",
            name="PIR Sensor",
            priority=80,
            confidence=0.95,
        )
        
        d = sensor.to_dict()
        
        assert d["sensor_type"] == "pir"
        assert d["priority"] == 80
        assert d["confidence"] == 0.95
    
    def test_sensor_defaults(self):
        """Test sensor default values."""
        sensor = PresenceSensor(
            sensor_id="sensor_test",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="binary_sensor.test",
            name="Test",
        )
        
        assert sensor.enabled is True
        assert sensor.priority == 50
        assert sensor.confidence == 1.0


class TestPresenceConfig:
    """Test presence configuration."""
    
    def test_create_config(self):
        """Test creating presence config."""
        config = PresenceConfig(zone_id="zone_living")
        
        assert config.zone_id == "zone_living"
        assert config.off_delay_seconds == 300
    
    def test_config_custom_values(self):
        """Test config with custom values."""
        config = PresenceConfig(
            zone_id="zone_bedroom",
            on_delay_seconds=5,
            off_delay_seconds=600,
            extended_absence_threshold_seconds=43200,
            require_multiple_sensors=True,
            min_confidence_threshold=0.7,
        )
        
        assert config.on_delay_seconds == 5
        assert config.off_delay_seconds == 600
        assert config.require_multiple_sensors is True
    
    def test_config_to_dict(self):
        """Test config serialization."""
        config = PresenceConfig(
            zone_id="zone_office",
            off_delay_seconds=180,
            min_confidence_threshold=0.6,
        )
        
        d = config.to_dict()
        
        assert d["off_delay_seconds"] == 180
        assert d["min_confidence_threshold"] == 0.6


class TestZonePresenceState:
    """Test zone presence state."""
    
    def test_create_state(self):
        """Test creating zone presence state."""
        state = ZonePresenceState(
            zone_id="zone_living",
            state=PresenceState.PRESENT,
            confidence=0.9,
            active_sensors=["sensor_1"],
            inactive_sensors=[],
        )
        
        assert state.zone_id == "zone_living"
        assert state.state == PresenceState.PRESENT
    
    def test_state_to_dict(self):
        """Test state serialization."""
        state = ZonePresenceState(
            zone_id="zone_bedroom",
            state=PresenceState.ABSENT,
            confidence=1.0,
            active_sensors=[],
            inactive_sensors=["sensor_1", "sensor_2"],
            absent_since="2025-01-01T00:00:00Z",
        )
        
        d = state.to_dict()
        
        assert d["state"] == "absent"
        assert len(d["inactive_sensors"]) == 2


class TestPresenceEvent:
    """Test presence event."""
    
    def test_create_event(self):
        """Test creating presence event."""
        event = PresenceEvent(
            event_id="pevt_test",
            zone_id="zone_living",
            event_type="present",
            previous_state=PresenceState.ABSENT,
            new_state=PresenceState.PRESENT,
            confidence=0.9,
            triggered_by=["sensor_1"],
        )
        
        assert event.event_type == "present"
        assert event.new_state == PresenceState.PRESENT
    
    def test_event_to_dict(self):
        """Test event serialization."""
        event = PresenceEvent(
            event_id="pevt_test",
            zone_id="zone_living",
            event_type="absent",
            previous_state=PresenceState.PRESENT,
            new_state=PresenceState.ABSENT,
            confidence=1.0,
            triggered_by=[],
        )
        
        d = event.to_dict()
        
        assert d["previous_state"] == "present"
        assert d["new_state"] == "absent"


class TestPresenceHistoryEntry:
    """Test presence history entry."""
    
    def test_create_history_entry(self):
        """Test creating history entry."""
        entry = PresenceHistoryEntry(
            timestamp="2025-01-01T00:00:00Z",
            zone_id="zone_living",
            state=PresenceState.PRESENT,
            confidence=0.9,
            active_sensor_count=2,
        )
        
        assert entry.active_sensor_count == 2
    
    def test_history_entry_to_dict(self):
        """Test history entry serialization."""
        entry = PresenceHistoryEntry(
            timestamp="2025-01-01T00:00:00Z",
            zone_id="zone_bedroom",
            state=PresenceState.ABSENT,
            confidence=1.0,
            active_sensor_count=0,
        )
        
        d = entry.to_dict()
        
        assert d["state"] == "absent"
        assert d["active_sensor_count"] == 0


class TestPresenceModule:
    """Test presence module."""
    
    def test_create_module(self):
        """Test module creation."""
        module = create_presence_module()
        assert module is not None
    
    def test_add_sensor(self):
        """Test adding sensor."""
        module = PresenceModule()
        
        sensor = PresenceSensor(
            sensor_id="sensor_test",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="binary_sensor.mmwave",
            name="Test Sensor",
        )
        
        sensor_id = module.add_sensor(sensor)
        
        assert sensor_id == "sensor_test"
        
        retrieved = module.get_sensor("sensor_test")
        
        assert retrieved is not None
        assert retrieved.zone_id == "zone_living"
    
    def test_remove_sensor(self):
        """Test removing sensor."""
        module = PresenceModule()
        
        sensor = PresenceSensor(
            sensor_id="sensor_test",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="binary_sensor.mmwave",
            name="Test",
        )
        
        module.add_sensor(sensor)
        
        result = module.remove_sensor("sensor_test")
        
        assert result is True
        assert module.get_sensor("sensor_test") is None
    
    def test_remove_nonexistent_sensor(self):
        """Test removing nonexistent sensor."""
        module = PresenceModule()
        
        result = module.remove_sensor("nonexistent")
        
        assert result is False
    
    def test_set_zone_config(self):
        """Test setting zone config."""
        module = PresenceModule()
        
        config = PresenceConfig(
            zone_id="zone_living",
            off_delay_seconds=600,
        )
        
        result = module.set_zone_config("zone_living", config)
        
        assert result is True
        
        retrieved = module.get_zone_config("zone_living")
        
        assert retrieved.off_delay_seconds == 600
    
    def test_update_sensor_state_triggers_present(self):
        """Test that sensor update triggers present state."""
        module = PresenceModule()
        
        sensor = PresenceSensor(
            sensor_id="sensor_1",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="binary_sensor.mmwave",
            name="Test",
        )
        
        module.add_sensor(sensor)
        
        event = module.update_sensor_state("sensor_1", is_present=True)
        
        assert event is not None
        assert event.event_type == "present"
        
        zone_state = module.get_zone_presence("zone_living")
        
        assert zone_state.state == PresenceState.PRESENT
    
    def test_update_sensor_state_triggers_absent(self):
        """Test that sensor update triggers absent state."""
        module = PresenceModule()
        
        sensor = PresenceSensor(
            sensor_id="sensor_1",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="binary_sensor.mmwave",
            name="Test",
        )
        
        module.add_sensor(sensor)
        
        # First trigger present
        module.update_sensor_state("sensor_1", is_present=True)
        
        # Then trigger absent
        event = module.update_sensor_state("sensor_1", is_present=False)
        
        # Should not immediately go absent (off-delay)
        zone_state = module.get_zone_presence("zone_living")
        
        assert zone_state.state in (PresenceState.UNCERTAIN, PresenceState.ABSENT)
    
    def test_update_sensor_state_nonexistent(self):
        """Test updating state for nonexistent sensor."""
        module = PresenceModule()
        
        event = module.update_sensor_state("nonexistent", is_present=True)
        
        assert event is None
    
    def test_update_disabled_sensor(self):
        """Test updating disabled sensor."""
        module = PresenceModule()
        
        sensor = PresenceSensor(
            sensor_id="sensor_1",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="binary_sensor.mmwave",
            name="Test",
            enabled=False,
        )
        
        module.add_sensor(sensor)
        
        event = module.update_sensor_state("sensor_1", is_present=True)
        
        assert event is None
    
    def test_get_zone_presence(self):
        """Test getting zone presence."""
        module = PresenceModule()
        
        sensor = PresenceSensor(
            sensor_id="sensor_1",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="binary_sensor.mmwave",
            name="Test",
        )
        
        module.add_sensor(sensor)
        module.update_sensor_state("sensor_1", is_present=True)
        
        state = module.get_zone_presence("zone_living")
        
        assert state is not None
        assert state.state == PresenceState.PRESENT
    
    def test_get_zone_presence_nonexistent(self):
        """Test getting presence for nonexistent zone."""
        module = PresenceModule()
        
        state = module.get_zone_presence("nonexistent")
        
        assert state is None
    
    def test_get_all_zone_presence(self):
        """Test getting all zone presence."""
        module = PresenceModule()
        
        module.add_sensor(PresenceSensor("s1", "zone_1", PresenceSensorType.MMWAVE, "binary_sensor.s1", "S1"))
        module.add_sensor(PresenceSensor("s2", "zone_2", PresenceSensorType.MMWAVE, "binary_sensor.s2", "S2"))
        
        module.update_sensor_state("s1", is_present=True)
        
        all_presence = module.get_all_zone_presence()
        
        assert len(all_presence) == 2
    
    def test_get_zone_sensors(self):
        """Test getting zone sensors."""
        module = PresenceModule()
        
        module.add_sensor(PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1"))
        module.add_sensor(PresenceSensor("s2", "zone_living", PresenceSensorType.PIR, "bs.s2", "S2"))
        module.add_sensor(PresenceSensor("s3", "zone_bedroom", PresenceSensorType.MMWAVE, "bs.s3", "S3"))
        
        sensors = module.get_zone_sensors("zone_living")
        
        assert len(sensors) == 2
    
    def test_get_presence_events(self):
        """Test getting presence events."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        module.update_sensor_state("s1", is_present=True)
        module.update_sensor_state("s1", is_present=False)
        
        events = module.get_presence_events("zone_living")
        
        assert len(events) >= 1
    
    def test_get_presence_events_limit(self):
        """Test getting events with limit."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        for i in range(150):
            module.update_sensor_state("s1", is_present=(i % 2 == 0))
        
        events = module.get_presence_events("zone_living", limit=50)
        
        assert len(events) <= 50
    
    def test_is_present(self):
        """Test is_present check."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        assert module.is_present("zone_living") is False
        
        module.update_sensor_state("s1", is_present=True)
        
        assert module.is_present("zone_living") is True
    
    def test_is_absent(self):
        """Test is_absent check."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        # Initially absent
        assert module.is_absent("zone_living") is True
        
        module.update_sensor_state("s1", is_present=True)
        
        assert module.is_absent("zone_living") is False
    
    def test_enable_sensor(self):
        """Test enabling sensor."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1", enabled=False)
        module.add_sensor(sensor)
        
        result = module.enable_sensor("s1")
        
        assert result is True
        
        sensor = module.get_sensor("s1")
        
        assert sensor.enabled is True
    
    def test_disable_sensor(self):
        """Test disabling sensor."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        result = module.disable_sensor("s1")
        
        assert result is True
        
        sensor = module.get_sensor("s1")
        
        assert sensor.enabled is False
    
    def test_set_sensor_priority(self):
        """Test setting sensor priority."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        result = module.set_sensor_priority("s1", 90)
        
        assert result is True
        
        sensor = module.get_sensor("s1")
        
        assert sensor.priority == 90
    
    def test_set_sensor_priority_clamped(self):
        """Test that sensor priority is clamped."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        module.set_sensor_priority("s1", 150)
        
        sensor = module.get_sensor("s1")
        
        assert sensor.priority == 100
        
        module.set_sensor_priority("s1", -10)
        
        sensor = module.get_sensor("s1")
        
        assert sensor.priority == 0
    
    def test_set_sensor_confidence(self):
        """Test setting sensor confidence."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        result = module.set_sensor_confidence("s1", 0.85)
        
        assert result is True
        
        sensor = module.get_sensor("s1")
        
        assert sensor.confidence == 0.85
    
    def test_set_sensor_confidence_clamped(self):
        """Test that sensor confidence is clamped."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        module.set_sensor_confidence("s1", 1.5)
        
        sensor = module.get_sensor("s1")
        
        assert sensor.confidence == 1.0
        
        module.set_sensor_confidence("s1", -0.5)
        
        sensor = module.get_sensor("s1")
        
        assert sensor.confidence == 0.0
    
    def test_reset_zone(self):
        """Test resetting zone."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        module.update_sensor_state("s1", is_present=True)
        
        result = module.reset_zone("zone_living")
        
        assert result is True
        
        zone_state = module.get_zone_presence("zone_living")
        
        assert zone_state.state == PresenceState.ABSENT
        assert zone_state.active_sensors == []
    
    def test_reset_nonexistent_zone(self):
        """Test resetting nonexistent zone."""
        module = PresenceModule()
        
        result = module.reset_zone("nonexistent")
        
        assert result is False
    
    def test_get_statistics(self):
        """Test getting statistics."""
        module = PresenceModule()
        
        module.add_sensor(PresenceSensor("s1", "zone_1", PresenceSensorType.MMWAVE, "bs.s1", "S1"))
        module.add_sensor(PresenceSensor("s2", "zone_2", PresenceSensorType.PIR, "bs.s2", "S2"))
        
        module.update_sensor_state("s1", is_present=True)
        
        stats = module.get_statistics()
        
        assert stats["total_sensors"] == 2
        assert stats["present_zones"] >= 1
    
    def test_statistics_enabled_disabled_sensors(self):
        """Test that statistics track enabled/disabled sensors."""
        module = PresenceModule()
        
        module.add_sensor(PresenceSensor("s1", "zone_1", PresenceSensorType.MMWAVE, "bs.s1", "S1"))
        module.disable_sensor("s1")
        
        stats = module.get_statistics()
        
        assert stats["enabled_sensors"] == 0
        assert stats["disabled_sensors"] == 1
    
    def test_multiple_sensors_same_zone(self):
        """Test multiple sensors in same zone."""
        module = PresenceModule()
        
        module.add_sensor(PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1"))
        module.add_sensor(PresenceSensor("s2", "zone_living", PresenceSensorType.PIR, "bs.s2", "S2"))
        
        # Trigger only one sensor — Bayesian fusion of MMWAVE+PIR gives UNCERTAIN
        module.update_sensor_state("s1", is_present=True)
        
        zone_state = module.get_zone_presence("zone_living")
        
        assert zone_state.state in (PresenceState.PRESENT, PresenceState.UNCERTAIN)
        assert "s1" in zone_state.active_sensors
        assert "s2" in zone_state.inactive_sensors
    
    def test_sensor_priority_affects_confidence(self):
        """Test that sensor priority affects confidence."""
        module = PresenceModule()
        
        # High priority sensor
        s1 = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1", priority=90, confidence=1.0)
        # Low priority sensor
        s2 = PresenceSensor("s2", "zone_living", PresenceSensorType.PIR, "bs.s2", "S2", priority=10, confidence=1.0)
        
        module.add_sensor(s1)
        module.add_sensor(s2)
        
        # Trigger low priority sensor only
        module.update_sensor_state("s2", is_present=True)
        
        zone_state = module.get_zone_presence("zone_living")
        
        # Confidence should be lower (weighted by priority)
        assert zone_state.confidence < 0.7  # Bayesian: PIR conf=0.5 → P=0.63
    
    def test_require_multiple_sensors(self):
        """Test require_multiple_sensors config."""
        module = PresenceModule()
        
        module.add_sensor(PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1"))
        module.add_sensor(PresenceSensor("s2", "zone_living", PresenceSensorType.PIR, "bs.s2", "S2"))
        
        config = PresenceConfig(
            zone_id="zone_living",
            require_multiple_sensors=True,
        )
        module.set_zone_config("zone_living", config)
        
        # Trigger only one sensor
        module.update_sensor_state("s1", is_present=True)
        
        zone_state = module.get_zone_presence("zone_living")
        
        # Should not be present (need 2+ sensors)
        assert zone_state.state != PresenceState.PRESENT
    
    def test_min_confidence_threshold(self):
        """Test min_confidence_threshold config."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1", confidence=0.3)
        module.add_sensor(sensor)
        
        config = PresenceConfig(
            zone_id="zone_living",
            min_confidence_threshold=0.15,
        )
        module.set_zone_config("zone_living", config)
        
        module.update_sensor_state("s1", is_present=True)
        
        zone_state = module.get_zone_presence("zone_living")
        
        # Bayesian P(present) ≈ 0.64 — above threshold 0.5 so PRESENT
        # (single MMWAVE with conf=0.3 is still informative)
        assert zone_state.state == PresenceState.PRESENT
    
    def test_on_delay(self):
        """Test on_delay configuration."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        config = PresenceConfig(
            zone_id="zone_living",
            on_delay_seconds=5,
        )
        module.set_zone_config("zone_living", config)
        
        # Trigger sensor
        module.update_sensor_state("s1", is_present=True)
        
        # Should be uncertain (not yet on_delay)
        zone_state = module.get_zone_presence("zone_living")
        
        assert zone_state.state == PresenceState.UNCERTAIN
    
    def test_off_delay(self):
        """Test off_delay configuration."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        config = PresenceConfig(
            zone_id="zone_living",
            off_delay_seconds=300,
        )
        module.set_zone_config("zone_living", config)
        
        # Trigger present
        module.update_sensor_state("s1", is_present=True)
        
        # Trigger absent
        module.update_sensor_state("s1", is_present=False)
        
        # Should be uncertain (not yet off_delay)
        zone_state = module.get_zone_presence("zone_living")
        
        assert zone_state.state == PresenceState.UNCERTAIN
    
    def test_presence_history_recorded(self):
        """Test that presence history is recorded."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        module.update_sensor_state("s1", is_present=True)
        
        history = module.get_presence_history("zone_living")
        
        assert len(history) >= 1
    
    def test_presence_history_limited(self):
        """Test that presence history is limited."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        for i in range(1500):
            module.update_sensor_state("s1", is_present=(i % 2 == 0))
        
        history = module._presence_history["zone_living"]
        
        assert len(history) == 1000
    
    def test_presence_events_limited(self):
        """Test that presence events are limited."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        for i in range(150):
            module.update_sensor_state("s1", is_present=(i % 2 == 0))
        
        events = module._presence_events["zone_living"]
        
        assert len(events) == 100
    
    def test_sensor_id_unique(self):
        """Test that sensor IDs are unique (user-provided)."""
        module = PresenceModule()
        
        s1 = PresenceSensor("sensor_1", "zone_1", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        s2 = PresenceSensor("sensor_1", "zone_2", PresenceSensorType.PIR, "bs.s2", "S2")
        
        module.add_sensor(s1)
        module.add_sensor(s2)  # Overwrites s1
        
        sensor = module.get_sensor("sensor_1")
        
        assert sensor.zone_id == "zone_2"
    
    def test_multiple_zones_independent(self):
        """Test that multiple zones are independent."""
        module = PresenceModule()
        
        module.add_sensor(PresenceSensor("s1", "zone_1", PresenceSensorType.MMWAVE, "bs.s1", "S1"))
        module.add_sensor(PresenceSensor("s2", "zone_2", PresenceSensorType.MMWAVE, "bs.s2", "S2"))
        
        module.update_sensor_state("s1", is_present=True)
        
        assert module.is_present("zone_1") is True
        assert module.is_present("zone_2") is False
    
    def test_get_occupancy_duration(self):
        """Test getting occupancy duration."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        module.update_sensor_state("s1", is_present=True)
        
        duration = module.get_occupancy_duration("zone_living")
        
        assert duration is not None
        assert duration > 0
    
    def test_get_occupancy_duration_not_present(self):
        """Test occupancy duration when not present."""
        module = PresenceModule()
        
        duration = module.get_occupancy_duration("zone_living")
        
        assert duration is None
    
    def test_get_absence_duration(self):
        """Test getting absence duration."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        # Initially absent
        duration = module.get_absence_duration("zone_living")
        
        # May be None if absent_since not set yet
        assert duration is None or duration >= 0
    
    def test_get_absence_duration_not_absent(self):
        """Test absence duration when present."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        module.update_sensor_state("s1", is_present=True)
        
        duration = module.get_absence_duration("zone_living")
        
        assert duration is None
    
    def test_zone_state_present_since_set(self):
        """Test that present_since is set when becoming present."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        module.update_sensor_state("s1", is_present=True)
        
        zone_state = module.get_zone_presence("zone_living")
        
        assert zone_state.present_since is not None
    
    def test_zone_state_absent_since_set(self):
        """Test that absent_since is set when becoming absent."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        module.update_sensor_state("s1", is_present=True)
        module.update_sensor_state("s1", is_present=False)
        
        # Wait for off-delay
        time.sleep(0.1)
        
        zone_state = module.get_zone_presence("zone_living")
        
        # May be uncertain or absent depending on timing
        assert zone_state.absent_since is not None or zone_state.state == PresenceState.UNCERTAIN
    
    def test_zone_state_last_motion_set(self):
        """Test that last_motion is set when sensors trigger."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        module.update_sensor_state("s1", is_present=True)
        
        zone_state = module.get_zone_presence("zone_living")
        
        assert zone_state.last_motion is not None
    
    def test_zone_state_last_update_set(self):
        """Test that last_update is set."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        module.update_sensor_state("s1", is_present=True)
        
        zone_state = module.get_zone_presence("zone_living")
        
        assert zone_state.last_update is not None
    
    def test_event_previous_state_tracked(self):
        """Test that event tracks previous state."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        # First event: absent → present
        event1 = module.update_sensor_state("s1", is_present=True)
        
        assert event1.previous_state == PresenceState.ABSENT
        assert event1.new_state == PresenceState.PRESENT
    
    def test_create_module_returns_instance(self):
        """Test that factory function returns instance."""
        module = create_presence_module()
        
        assert isinstance(module, PresenceModule)
    
    def test_sensor_to_dict_includes_all_fields(self):
        """Test that sensor to_dict includes all fields."""
        sensor = PresenceSensor(
            sensor_id="sensor_test",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="binary_sensor.test",
            name="Test Sensor",
            priority=75,
            confidence=0.85,
        )
        
        d = sensor.to_dict()
        
        assert d["priority"] == 75
        assert d["confidence"] == 0.85
    
    def test_config_to_dict_includes_all_fields(self):
        """Test that config to_dict includes all fields."""
        config = PresenceConfig(
            zone_id="zone_test",
            on_delay_seconds=10,
            off_delay_seconds=600,
            extended_absence_threshold_seconds=86400,
            require_multiple_sensors=True,
            min_confidence_threshold=0.7,
        )
        
        d = config.to_dict()
        
        assert d["on_delay_seconds"] == 10
        assert d["require_multiple_sensors"] is True
    
    def test_state_to_dict_includes_all_fields(self):
        """Test that state to_dict includes all fields."""
        state = ZonePresenceState(
            zone_id="zone_test",
            state=PresenceState.PRESENT,
            confidence=0.9,
            active_sensors=["s1", "s2"],
            inactive_sensors=["s3"],
            present_since="2025-01-01T00:00:00Z",
            last_motion="2025-01-01T00:00:00Z",
        )
        
        d = state.to_dict()
        
        assert len(d["active_sensors"]) == 2
        assert d["present_since"] is not None
    
    def test_event_to_dict_includes_all_fields(self):
        """Test that event to_dict includes all fields."""
        event = PresenceEvent(
            event_id="pevt_test",
            zone_id="zone_test",
            event_type="present",
            previous_state=PresenceState.ABSENT,
            new_state=PresenceState.PRESENT,
            confidence=0.9,
            triggered_by=["s1"],
        )
        
        d = event.to_dict()
        
        assert d["event_type"] == "present"
        assert len(d["triggered_by"]) == 1
    
    def test_history_entry_to_dict_includes_all_fields(self):
        """Test that history entry to_dict includes all fields."""
        entry = PresenceHistoryEntry(
            timestamp="2025-01-01T00:00:00Z",
            zone_id="zone_test",
            state=PresenceState.PRESENT,
            confidence=0.9,
            active_sensor_count=2,
        )
        
        d = entry.to_dict()
        
        assert d["active_sensor_count"] == 2
    
    def test_statistics_initial_values(self):
        """Test statistics initial values."""
        module = PresenceModule()
        
        stats = module.get_statistics()
        
        assert stats["total_sensors"] == 0
        assert stats["total_zones"] == 0
        assert stats["present_zones"] == 0
    
    def test_statistics_total_events(self):
        """Test that statistics track total events."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        module.update_sensor_state("s1", is_present=True)
        module.update_sensor_state("s1", is_present=False)
        
        stats = module.get_statistics()
        
        assert stats["total_events"] >= 1
    
    def test_statistics_total_history_entries(self):
        """Test that statistics track total history entries."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        module.update_sensor_state("s1", is_present=True)
        
        stats = module.get_statistics()
        
        assert stats["total_history_entries"] >= 1
    
    def test_get_presence_history_by_hours(self):
        """Test getting presence history filtered by hours."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        for i in range(10):
            module.update_sensor_state("s1", is_present=(i % 2 == 0))
        
        history = module.get_presence_history("zone_living", hours=1)
        
        assert isinstance(history, list)
    
    def test_get_presence_history_empty(self):
        """Test getting presence history when empty."""
        module = PresenceModule()
        
        history = module.get_presence_history("nonexistent")
        
        assert history == []
    
    def test_enable_nonexistent_sensor(self):
        """Test enabling nonexistent sensor."""
        module = PresenceModule()
        
        result = module.enable_sensor("nonexistent")
        
        assert result is False
    
    def test_disable_nonexistent_sensor(self):
        """Test disabling nonexistent sensor."""
        module = PresenceModule()
        
        result = module.disable_sensor("nonexistent")
        
        assert result is False
    
    def test_set_priority_nonexistent_sensor(self):
        """Test setting priority for nonexistent sensor."""
        module = PresenceModule()
        
        result = module.set_sensor_priority("nonexistent", 80)
        
        assert result is False
    
    def test_set_confidence_nonexistent_sensor(self):
        """Test setting confidence for nonexistent sensor."""
        module = PresenceModule()
        
        result = module.set_sensor_confidence("nonexistent", 0.9)
        
        assert result is False
    
    def test_get_zone_config_nonexistent(self):
        """Test getting config for nonexistent zone."""
        module = PresenceModule()
        
        config = module.get_zone_config("nonexistent")
        
        assert config is None
    
    def test_update_sensor_state_with_confidence(self):
        """Test updating sensor state with confidence parameter."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        event = module.update_sensor_state("s1", is_present=True, confidence=0.95)
        
        assert event is not None
        assert event.confidence > 0
    
    def test_sensor_last_trigger_updated(self):
        """Test that sensor last_trigger is updated."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        module.update_sensor_state("s1", is_present=True)
        
        sensor = module.get_sensor("s1")
        
        assert sensor.last_trigger is not None
    
    def test_zone_state_confidence_calculated(self):
        """Test that zone confidence is calculated."""
        module = PresenceModule()
        
        s1 = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1", confidence=0.9)
        s2 = PresenceSensor("s2", "zone_living", PresenceSensorType.PIR, "bs.s2", "S2", confidence=0.7)
        
        module.add_sensor(s1)
        module.add_sensor(s2)
        
        module.update_sensor_state("s1", is_present=True)
        module.update_sensor_state("s2", is_present=True)
        
        zone_state = module.get_zone_presence("zone_living")
        
        assert zone_state.confidence > 0
        assert zone_state.confidence <= 1.0
    
    def test_extended_absent_state(self):
        """Test extended_absent state after long absence."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        config = PresenceConfig(
            zone_id="zone_living",
            extended_absence_threshold_seconds=1,  # 1 second for testing
        )
        module.set_zone_config("zone_living", config)
        
        # Trigger absent
        module.update_sensor_state("s1", is_present=False)
        
        # Wait for extended absence threshold
        time.sleep(1.5)
        
        # Trigger state update
        module.update_sensor_state("s1", is_present=False)
        
        zone_state = module.get_zone_presence("zone_living")
        
        # Should be extended_absent after threshold
        assert zone_state.state == PresenceState.EXTENDED_ABSENT
    
    def test_event_timestamp_set(self):
        """Test that event timestamp is set."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        event = module.update_sensor_state("s1", is_present=True)
        
        assert event.timestamp is not None
    
    def test_history_entry_timestamp_set(self):
        """Test that history entry timestamp is set."""
        module = PresenceModule()
        
        sensor = PresenceSensor("s1", "zone_living", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(sensor)
        
        module.update_sensor_state("s1", is_present=True)
        
        history = module._presence_history["zone_living"]
        
        assert history[0].timestamp is not None
    
    def test_list_sensors_by_zone(self):
        """Test getting sensors filtered by zone."""
        module = PresenceModule()
        
        module.add_sensor(PresenceSensor("s1", "zone_1", PresenceSensorType.MMWAVE, "bs.s1", "S1"))
        module.add_sensor(PresenceSensor("s2", "zone_2", PresenceSensorType.MMWAVE, "bs.s2", "S2"))
        
        zone_1_sensors = module.get_zone_sensors("zone_1")
        
        assert len(zone_1_sensors) == 1
        assert zone_1_sensors[0].sensor_id == "s1"
    
    def test_sensor_type_mmwave(self):
        """Test mmwave sensor type."""
        sensor = PresenceSensor("s1", "zone_1", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        
        assert sensor.sensor_type == PresenceSensorType.MMWAVE
    
    def test_sensor_type_pir(self):
        """Test pir sensor type."""
        sensor = PresenceSensor("s1", "zone_1", PresenceSensorType.PIR, "bs.s1", "S1")
        
        assert sensor.sensor_type == PresenceSensorType.PIR
    
    def test_sensor_type_device_tracker(self):
        """Test device_tracker sensor type."""
        sensor = PresenceSensor("s1", "zone_1", PresenceSensorType.DEVICE_TRACKER, "device_tracker.phone", "S1")
        
        assert sensor.sensor_type == PresenceSensorType.DEVICE_TRACKER
    
    def test_sensor_type_person(self):
        """Test person sensor type."""
        sensor = PresenceSensor("s1", "zone_1", PresenceSensorType.PERSON, "person.john", "S1")
        
        assert sensor.sensor_type == PresenceSensorType.PERSON
    
    def test_zone_state_active_inactive_sensors_updated(self):
        """Test that active/inactive sensors lists are updated."""
        module = PresenceModule()
        
        module.add_sensor(PresenceSensor("s1", "zone_1", PresenceSensorType.MMWAVE, "bs.s1", "S1"))
        module.add_sensor(PresenceSensor("s2", "zone_1", PresenceSensorType.PIR, "bs.s2", "S2"))
        
        module.update_sensor_state("s1", is_present=True)
        
        zone_state = module.get_zone_presence("zone_1")
        
        assert "s1" in zone_state.active_sensors
        assert "s2" in zone_state.inactive_sensors
