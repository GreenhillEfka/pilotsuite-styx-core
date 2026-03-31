"""Tests for Presence Module Extensions — Slice 75."""
import pytest
from copilot_core.presence.presence_extended import (
    PresenceModuleExtended,
    AdvancedSensorConfig,
    SensorReading,
    PresenceProfile,
    OccupancyTrend,
    MultiPersonState,
    PresenceSensorType,
    PresencePattern,
    create_presence_module_extended,
)
from datetime import datetime, timezone, timedelta


class TestPresenceSensorType:
    def test_sensor_type_enum_values(self):
        assert PresenceSensorType.MMWAVE.value == "mmwave"
        assert PresenceSensorType.PIR.value == "pir"
        assert PresenceSensorType.CAMERA.value == "camera"
        assert PresenceSensorType.BLE.value == "ble"
        assert PresenceSensorType.WIFI.value == "wifi"


class TestPresencePattern:
    def test_pattern_enum_values(self):
        assert PresencePattern.TYPICAL_MORNING.value == "typical_morning"
        assert PresencePattern.AWAY_PATTERN.value == "away_pattern"
        assert PresencePattern.GUEST_PATTERN.value == "guest_pattern"


class TestAdvancedSensorConfig:
    def test_create_config(self):
        config = AdvancedSensorConfig(
            sensor_id="sensor_1",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="binary_sensor.mmwave",
            name="Living mmWave",
        )
        assert config.enabled is True
        assert config.priority == 50
    
    def test_config_custom_values(self):
        config = AdvancedSensorConfig(
            sensor_id="sensor_1",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="binary_sensor.mmwave",
            name="Living mmWave",
            priority=80,
            confidence=0.9,
            weight=1.5,
            min_trigger_time_seconds=5,
            pet_friendly=True,
        )
        assert config.priority == 80
        assert config.weight == 1.5
    
    def test_config_to_dict(self):
        config = AdvancedSensorConfig(
            sensor_id="sensor_1",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.PIR,
            entity_id="binary_sensor.pir",
            name="PIR Sensor",
            battery_monitored=True,
        )
        d = config.to_dict()
        assert d["sensor_type"] == "pir"
        assert d["battery_monitored"] is True


class TestSensorReading:
    def test_create_reading(self):
        reading = SensorReading(
            reading_id="sr_test",
            sensor_id="sensor_1",
            zone_id="zone_living",
            timestamp="2025-01-01T00:00:00Z",
            is_present=True,
            confidence=0.9,
        )
        assert reading.is_present is True
    
    def test_reading_to_dict(self):
        reading = SensorReading(
            reading_id="sr_test",
            sensor_id="sensor_1",
            zone_id="zone_living",
            timestamp="2025-01-01T00:00:00Z",
            is_present=False,
            battery_level=85,
        )
        d = reading.to_dict()
        assert d["battery_level"] == 85


class TestPresenceProfile:
    def test_create_profile(self):
        profile = PresenceProfile(
            profile_id="profile_1",
            zone_id="zone_living",
            name="Living Room Profile",
        )
        assert profile.sensitivity_multiplier == 1.0
        assert profile.guest_mode_enabled is False
    
    def test_profile_with_typical_hours(self):
        profile = PresenceProfile(
            profile_id="profile_1",
            zone_id="zone_living",
            name="Living Profile",
            typical_occupancy_hours=[8, 9, 10, 18, 19, 20],
            typical_absence_hours=[0, 1, 2, 3, 4, 5, 11, 12, 13, 14, 15, 16, 17],
        )
        assert 8 in profile.typical_occupancy_hours
        assert 3 in profile.typical_absence_hours
    
    def test_profile_to_dict(self):
        profile = PresenceProfile(
            profile_id="profile_1",
            zone_id="zone_living",
            name="Test",
            pet_friendly=True,
            sensitivity_multiplier=1.2,
        )
        d = profile.to_dict()
        assert d["pet_friendly"] is True
        assert d["sensitivity_multiplier"] == 1.2


class TestMultiPersonState:
    def test_create_state(self):
        state = MultiPersonState(zone_id="zone_living")
        assert state.person_count == 0
    
    def test_state_with_persons(self):
        state = MultiPersonState(
            zone_id="zone_living",
            person_count=3,
            known_persons={"person_1", "person_2"},
            unknown_persons=1,
        )
        assert state.person_count == 3
        assert len(state.known_persons) == 2
    
    def test_state_to_dict(self):
        state = MultiPersonState(
            zone_id="zone_living",
            person_count=2,
            known_persons={"person_1"},
        )
        d = state.to_dict()
        assert d["person_count"] == 2


class TestPresenceModuleExtended:
    def test_create_module(self):
        module = create_presence_module_extended()
        assert module is not None
    
    def test_add_sensor(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig(
            sensor_id="sensor_1",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="binary_sensor.mmwave",
            name="Living mmWave",
        )
        
        sensor_id = module.add_sensor(config)
        
        assert sensor_id == "sensor_1"
        assert module.get_sensor("sensor_1") is not None
    
    def test_remove_sensor(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig(
            sensor_id="sensor_1",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="binary_sensor.mmwave",
            name="Test",
        )
        
        module.add_sensor(config)
        
        result = module.remove_sensor("sensor_1")
        
        assert result is True
        assert module.get_sensor("sensor_1") is None
    
    def test_remove_nonexistent_sensor(self):
        module = PresenceModuleExtended()
        
        result = module.remove_sensor("nonexistent")
        
        assert result is False
    
    def test_set_zone_profile(self):
        module = PresenceModuleExtended()
        
        profile = PresenceProfile(
            profile_id="profile_1",
            zone_id="zone_living",
            name="Living Profile",
        )
        
        result = module.set_zone_profile(profile)
        
        assert result == "profile_1"
        assert module.get_zone_profile("zone_living") is not None
    
    def test_enable_guest_mode(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig(
            sensor_id="sensor_1",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="bs.mmwave",
            name="Test",
        )
        module.add_sensor(config)
        
        result = module.enable_guest_mode("zone_living")
        
        assert result is True
        assert module.is_guest_mode("zone_living") is True
    
    def test_disable_guest_mode(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig(
            sensor_id="sensor_1",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="bs.mmwave",
            name="Test",
        )
        module.add_sensor(config)
        module.enable_guest_mode("zone_living")
        
        result = module.disable_guest_mode("zone_living")
        
        assert result is True
        assert module.is_guest_mode("zone_living") is False
    
    def test_process_sensor_reading(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig(
            sensor_id="sensor_1",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="bs.mmwave",
            name="Test",
        )
        module.add_sensor(config)
        
        reading = module.process_sensor_reading("sensor_1", is_present=True, confidence=0.9)
        
        assert reading is not None
        assert reading.is_present is True
    
    def test_process_disabled_sensor(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig(
            sensor_id="sensor_1",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="bs.mmwave",
            name="Test",
            enabled=False,
        )
        module.add_sensor(config)
        
        reading = module.process_sensor_reading("sensor_1", is_present=True)
        
        assert reading is None
    
    def test_process_nonexistent_sensor(self):
        module = PresenceModuleExtended()
        
        reading = module.process_sensor_reading("nonexistent", is_present=True)
        
        assert reading is None
    
    def test_pet_filtering(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig(
            sensor_id="sensor_1",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="bs.mmwave",
            name="Test",
            ignore_motion_below=0.5,  # Ignore small motion
        )
        module.add_sensor(config)
        
        # Small motion (pet)
        reading = module.process_sensor_reading("sensor_1", is_present=True, raw_value=0.3)
        
        assert reading is None  # Filtered out
        
        # Large motion (person)
        reading = module.process_sensor_reading("sensor_1", is_present=True, raw_value=0.8)
        
        assert reading is not None
    
    def test_calculate_zone_presence_single_sensor(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig(
            sensor_id="sensor_1",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="bs.mmwave",
            name="Test",
            confidence=0.9,
        )
        module.add_sensor(config)
        
        module.process_sensor_reading("sensor_1", is_present=True)
        
        is_present, confidence = module.calculate_zone_presence("zone_living")
        
        assert is_present is True
        assert confidence > 0.5
    
    def test_calculate_zone_presence_no_sensors(self):
        module = PresenceModuleExtended()
        
        is_present, confidence = module.calculate_zone_presence("nonexistent")
        
        assert is_present is False
        assert confidence == 0.0
    
    def test_weighted_sensor_fusion(self):
        module = PresenceModuleExtended()
        
        # High weight sensor
        config1 = AdvancedSensorConfig(
            sensor_id="sensor_1",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="bs.mmwave1",
            name="High Weight",
            weight=2.0,
            confidence=1.0,
        )
        
        # Low weight sensor
        config2 = AdvancedSensorConfig(
            sensor_id="sensor_2",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.PIR,
            entity_id="bs.pir",
            name="Low Weight",
            weight=0.5,
            confidence=1.0,
        )
        
        module.add_sensor(config1)
        module.add_sensor(config2)
        
        # Only low weight sensor detects presence
        module.process_sensor_reading("sensor_1", is_present=False)
        module.process_sensor_reading("sensor_2", is_present=True)
        
        is_present, confidence = module.calculate_zone_presence("zone_living")
        
        # Should be lower confidence due to weight
        assert confidence < 0.5
    
    def test_guest_mode_threshold(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig(
            sensor_id="sensor_1",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="bs.mmwave",
            name="Test",
            confidence=0.4,  # Below normal threshold
        )
        module.add_sensor(config)
        module.enable_guest_mode("zone_living")
        
        module.process_sensor_reading("sensor_1", is_present=True)
        
        is_present, confidence = module.calculate_zone_presence("zone_living")
        
        # Guest mode has lower threshold (0.3)
        assert is_present is True
    
    def test_get_occupancy_trend(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig(
            sensor_id="sensor_1",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="bs.mmwave",
            name="Test",
        )
        module.add_sensor(config)
        
        # Generate readings
        for i in range(100):
            module.process_sensor_reading("sensor_1", is_present=(i % 3 == 0))
        
        trend = module.get_occupancy_trend("zone_living", hours=24)
        
        assert trend is not None
        assert trend.zone_id == "zone_living"
    
    def test_trend_occupancy_rate(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig(
            sensor_id="sensor_1",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="bs.mmwave",
            name="Test",
        )
        module.add_sensor(config)
        
        # All present
        for i in range(100):
            module.process_sensor_reading("sensor_1", is_present=True)
        
        trend = module.get_occupancy_trend("zone_living", hours=24)
        
        assert trend.occupancy_rate == 1.0
    
    def test_detect_pattern_away(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig(
            sensor_id="sensor_1",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="bs.mmwave",
            name="Test",
        )
        module.add_sensor(config)
        
        # All absent
        for i in range(100):
            module.process_sensor_reading("sensor_1", is_present=False)
        
        module.get_occupancy_trend("zone_living", hours=24)
        
        trend = module.get_trend("zone_living")
        
        assert trend.pattern_detected == PresencePattern.AWAY_PATTERN
    
    def test_multi_person_state_update(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig(
            sensor_id="person_john",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.PERSON,
            entity_id="person.john",
            name="John",
        )
        module.add_sensor(config)
        
        module.process_sensor_reading("person_john", is_present=True)
        
        state = module.get_multi_person_state("zone_living")
        
        assert state is not None
        assert state.person_count == 1
        assert "john" in state.known_persons
    
    def test_multi_person_state_leave(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig(
            sensor_id="person_john",
            zone_id="zone_living",
            sensor_type=PresenceSensorType.PERSON,
            entity_id="person.john",
            name="John",
        )
        module.add_sensor(config)
        
        module.process_sensor_reading("person_john", is_present=True)
        module.process_sensor_reading("person_john", is_present=False)
        
        state = module.get_multi_person_state("zone_living")
        
        assert state.person_count == 0
    
    def test_get_zone_sensors(self):
        module = PresenceModuleExtended()
        
        module.add_sensor(AdvancedSensorConfig("s1", "zone_1", PresenceSensorType.MMWAVE, "bs.s1", "S1"))
        module.add_sensor(AdvancedSensorConfig("s2", "zone_1", PresenceSensorType.PIR, "bs.s2", "S2"))
        module.add_sensor(AdvancedSensorConfig("s3", "zone_2", PresenceSensorType.MMWAVE, "bs.s3", "S3"))
        
        sensors = module.get_zone_sensors("zone_1")
        
        assert len(sensors) == 2
    
    def test_get_sensor_readings(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig("s1", "zone_1", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(config)
        
        for i in range(50):
            module.process_sensor_reading("s1", is_present=(i % 2 == 0))
        
        readings = module.get_sensor_readings("s1", limit=10)
        
        assert len(readings) == 10
    
    def test_readings_limited_to_1000(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig("s1", "zone_1", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(config)
        
        for i in range(1500):
            module.process_sensor_reading("s1", is_present=(i % 2 == 0))
        
        readings = module._readings["s1"]
        
        assert len(readings) == 1000
    
    def test_get_statistics(self):
        module = PresenceModuleExtended()
        
        module.add_sensor(AdvancedSensorConfig("s1", "zone_1", PresenceSensorType.MMWAVE, "bs.s1", "S1"))
        module.add_sensor(AdvancedSensorConfig("s2", "zone_1", PresenceSensorType.PIR, "bs.s2", "S2"))
        
        stats = module.get_statistics()
        
        assert stats["total_sensors"] == 2
        assert "mmwave" in stats["sensor_types"]
    
    def test_create_module_returns_instance(self):
        assert isinstance(create_presence_module_extended(), PresenceModuleExtended)
    
    def test_sensor_history_tracked(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig("s1", "zone_1", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(config)
        
        for i in range(50):
            module.process_sensor_reading("s1", is_present=(i % 2 == 0))
        
        history = module._sensor_history["s1"]
        
        assert len(history) == 50
    
    def test_sensor_history_limited_to_100(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig("s1", "zone_1", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(config)
        
        for i in range(150):
            module.process_sensor_reading("s1", is_present=(i % 2 == 0))
        
        history = module._sensor_history["s1"]
        
        assert len(history) == 100
    
    def test_tamper_detection(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig(
            "s1", "zone_1", PresenceSensorType.MMWAVE, "bs.s1", "S1",
            tamper_detection=True,
        )
        module.add_sensor(config)
        
        # Rapid state changes (tamper)
        for i in range(20):
            module.process_sensor_reading("s1", is_present=(i % 2 == 0))
        
        # Should detect tamper
        assert module._check_tamper("s1") is True
    
    def test_no_tamper_normal_use(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig(
            "s1", "zone_1", PresenceSensorType.MMWAVE, "bs.s1", "S1",
            tamper_detection=True,
        )
        module.add_sensor(config)
        
        # Normal use (few changes)
        for i in range(20):
            module.process_sensor_reading("s1", is_present=(i < 10))
        
        # Should not detect tamper
        assert module._check_tamper("s1") is False
    
    def test_confidence_decay(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig(
            "s1", "zone_1", PresenceSensorType.MMWAVE, "bs.s1", "S1",
            confidence=0.9,
            max_confidence_decay=0.5,  # High decay for testing
        )
        module.add_sensor(config)
        
        module.process_sensor_reading("s1", is_present=True, confidence=0.9)
        
        # Confidence should decay over time
        is_present, confidence = module.calculate_zone_presence("zone_1")
        
        # Confidence will be lower due to decay
        assert confidence < 0.9
    
    def test_profile_sensitivity_multiplier(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig(
            "s1", "zone_1", PresenceSensorType.MMWAVE, "bs.s1", "S1",
            confidence=0.6,
        )
        module.add_sensor(config)
        
        profile = PresenceProfile(
            profile_id="p1",
            zone_id="zone_1",
            name="High Sensitivity",
            sensitivity_multiplier=1.5,
        )
        module.set_zone_profile(profile)
        
        module.process_sensor_reading("s1", is_present=True)
        
        is_present, confidence = module.calculate_zone_presence("zone_1")
        
        # Sensitivity multiplier increases confidence
        assert confidence > 0.6
    
    def test_zone_profile_to_dict(self):
        profile = PresenceProfile(
            profile_id="p1",
            zone_id="zone_1",
            name="Test",
            typical_occupancy_hours=[8, 9, 10],
            weekend_behavior_different=True,
            auto_away_timeout_seconds=86400,
        )
        d = profile.to_dict()
        assert d["weekend_behavior_different"] is True
        assert d["auto_away_timeout_seconds"] == 86400
    
    def test_occupancy_trend_to_dict(self):
        trend = OccupancyTrend(
            zone_id="zone_1",
            period_start="2025-01-01T00:00:00Z",
            period_end="2025-01-02T00:00:00Z",
            total_occupied_minutes=720,
            total_absent_minutes=720,
            occupancy_rate=0.5,
            peak_occupancy_hour=18,
            lowest_occupancy_hour=3,
            average_confidence=0.8,
            pattern_detected=PresencePattern.TYPICAL_EVENING,
        )
        d = trend.to_dict()
        assert d["occupancy_rate"] == 0.5
        assert d["pattern_detected"] == "typical_evening"
    
    def test_advanced_sensor_config_to_dict(self):
        config = AdvancedSensorConfig(
            sensor_id="s1",
            zone_id="zone_1",
            sensor_type=PresenceSensorType.MMWAVE,
            entity_id="bs.s1",
            name="Test",
            priority=75,
            weight=1.5,
            min_trigger_time_seconds=5,
            battery_monitored=True,
        )
        d = config.to_dict()
        assert d["priority"] == 75
        assert d["weight"] == 1.5
    
    def test_sensor_reading_to_dict(self):
        reading = SensorReading(
            reading_id="sr_test",
            sensor_id="s1",
            zone_id="zone_1",
            timestamp="2025-01-01T00:00:00Z",
            is_present=True,
            confidence=0.9,
            battery_level=95,
        )
        d = reading.to_dict()
        assert d["battery_level"] == 95
    
    def test_multi_person_state_to_dict(self):
        state = MultiPersonState(
            zone_id="zone_1",
            person_count=3,
            known_persons={"p1", "p2"},
            unknown_persons=1,
        )
        d = state.to_dict()
        assert d["person_count"] == 3
        assert len(d["known_persons"]) == 2
    
    def test_get_trend_nonexistent_zone(self):
        module = PresenceModuleExtended()
        
        trend = module.get_trend("nonexistent")
        
        assert trend is None
    
    def test_get_multi_person_state_nonexistent_zone(self):
        module = PresenceModuleExtended()
        
        state = module.get_multi_person_state("nonexistent")
        
        assert state is None
    
    def test_is_guest_mode_nonexistent_zone(self):
        module = PresenceModuleExtended()
        
        result = module.is_guest_mode("nonexistent")
        
        assert result is False
    
    def test_enable_guest_mode_no_sensors(self):
        module = PresenceModuleExtended()
        
        result = module.enable_guest_mode("nonexistent")
        
        assert result is False
    
    def test_disable_guest_mode_not_enabled(self):
        module = PresenceModuleExtended()
        
        result = module.disable_guest_mode("zone_1")
        
        assert result is False
    
    def test_statistics_sensor_types(self):
        module = PresenceModuleExtended()
        
        module.add_sensor(AdvancedSensorConfig("s1", "z1", PresenceSensorType.MMWAVE, "bs.s1", "S1"))
        module.add_sensor(AdvancedSensorConfig("s2", "z1", PresenceSensorType.PIR, "bs.s2", "S2"))
        module.add_sensor(AdvancedSensorConfig("s3", "z1", PresenceSensorType.MMWAVE, "bs.s3", "S3"))
        
        stats = module.get_statistics()
        
        assert stats["sensor_types"]["mmwave"] == 2
        assert stats["sensor_types"]["pir"] == 1
    
    def test_statistics_guest_mode_zones(self):
        module = PresenceModuleExtended()
        
        module.add_sensor(AdvancedSensorConfig("s1", "z1", PresenceSensorType.MMWAVE, "bs.s1", "S1"))
        module.add_sensor(AdvancedSensorConfig("s2", "z2", PresenceSensorType.MMWAVE, "bs.s2", "S2"))
        
        module.enable_guest_mode("z1")
        module.enable_guest_mode("z2")
        
        stats = module.get_statistics()
        
        assert stats["guest_mode_zones"] == 2
    
    def test_pattern_detection_weekend(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig("s1", "zone_1", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(config)
        
        # High occupancy on weekend
        for i in range(100):
            module.process_sensor_reading("s1", is_present=True)
        
        module.get_occupancy_trend("zone_1", hours=24)
        
        trend = module.get_trend("zone_1")
        
        # Pattern detection depends on current time
        assert trend.pattern_detected is not None
    
    def test_trend_sensor_reliability(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig("s1", "zone_1", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(config)
        
        # Consistent readings
        for i in range(100):
            module.process_sensor_reading("s1", is_present=True)
        
        module.get_occupancy_trend("zone_1", hours=24)
        
        trend = module.get_trend("zone_1")
        
        assert "s1" in trend.sensor_reliability
        assert trend.sensor_reliability["s1"] > 0.9
    
    def test_get_occupancy_trend_no_readings(self):
        module = PresenceModuleExtended()
        
        config = AdvancedSensorConfig("s1", "zone_1", PresenceSensorType.MMWAVE, "bs.s1", "S1")
        module.add_sensor(config)
        
        trend = module.get_occupancy_trend("zone_1", hours=24)
        
        # No readings yet
        assert trend is None
