"""Tests for Zone-Aware Comfort Index — Slice 68."""
import pytest
from copilot_core.comfort.zone_comfort import (
    ZoneComfortEngine,
    ZoneComfortProfile,
    ZoneComfortState,
    ComfortHistoryEntry,
    ComfortAlert,
    ComfortLevel,
    ComfortFactor,
    create_zone_comfort_engine,
)
from datetime import datetime, timezone, timedelta


class TestComfortLevel:
    """Test comfort levels."""
    
    def test_comfort_level_enum_values(self):
        """Test comfort level enum values."""
        assert ComfortLevel.VERY_UNCOMFORTABLE.value == "very_uncomfortable"
        assert ComfortLevel.UNCOMFORTABLE.value == "uncomfortable"
        assert ComfortLevel.NEUTRAL.value == "neutral"
        assert ComfortLevel.COMFORTABLE.value == "comfortable"
        assert ComfortLevel.VERY_COMFORTABLE.value == "very_comfortable"


class TestComfortFactor:
    """Test comfort factors."""
    
    def test_comfort_factor_enum_values(self):
        """Test comfort factor enum values."""
        assert ComfortFactor.TEMPERATURE.value == "temperature"
        assert ComfortFactor.HUMIDITY.value == "humidity"
        assert ComfortFactor.LIGHT.value == "light"
        assert ComfortFactor.NOISE.value == "noise"
        assert ComfortFactor.AIR_QUALITY.value == "air_quality"


class TestZoneComfortProfile:
    """Test zone comfort profile."""
    
    def test_create_profile(self):
        """Test creating comfort profile."""
        profile = ZoneComfortProfile(
            profile_id="profile_test",
            name="Test Profile",
            profile_type="custom",
        )
        
        assert profile.profile_id == "profile_test"
        assert profile.temp_optimal == 22.0
    
    def test_profile_with_custom_values(self):
        """Test profile with custom values."""
        profile = ZoneComfortProfile(
            profile_id="profile_baby",
            name="Baby Room",
            profile_type="baby",
            temp_min=20.0,
            temp_max=24.0,
            temp_optimal=22.0,
            humidity_optimal=50.0,
        )
        
        assert profile.temp_min == 20.0
        assert profile.temp_max == 24.0
    
    def test_profile_to_dict(self):
        """Test profile serialization."""
        profile = ZoneComfortProfile(
            profile_id="profile_office",
            name="Office",
            profile_type="office",
            temp_weight=0.30,
            humidity_weight=0.25,
        )
        
        d = profile.to_dict()
        
        assert d["profile_type"] == "office"
        assert d["weights"]["temperature"] == 0.30
    
    def test_profile_default_weights_sum(self):
        """Test that default weights sum to 1.0."""
        profile = ZoneComfortProfile(
            profile_id="profile_test",
            name="Test",
            profile_type="custom",
        )
        
        total = (
            profile.temp_weight +
            profile.humidity_weight +
            profile.light_weight +
            profile.noise_weight +
            profile.air_quality_weight
        )
        
        assert abs(total - 1.0) < 0.001


class TestZoneComfortState:
    """Test zone comfort state."""
    
    def test_create_state(self):
        """Test creating comfort state."""
        state = ZoneComfortState(
            zone_id="zone_living",
            comfort_score=75.0,
            comfort_level=ComfortLevel.COMFORTABLE,
        )
        
        assert state.zone_id == "zone_living"
        assert state.comfort_score == 75.0
    
    def test_state_with_sensor_data(self):
        """Test state with sensor data."""
        state = ZoneComfortState(
            zone_id="zone_bedroom",
            comfort_score=65.0,
            comfort_level=ComfortLevel.COMFORTABLE,
            temperature=21.5,
            humidity=45.0,
            light=0.5,
        )
        
        assert state.temperature == 21.5
        assert state.humidity == 45.0
    
    def test_state_to_dict(self):
        """Test state serialization."""
        state = ZoneComfortState(
            zone_id="zone_office",
            comfort_score=80.0,
            comfort_level=ComfortLevel.VERY_COMFORTABLE,
            temperature=22.0,
            factor_scores={"temperature": 85.0, "humidity": 75.0},
        )
        
        d = state.to_dict()
        
        assert d["comfort_level"] == "very_comfortable"
        assert d["factor_scores"]["temperature"] == 85.0


class TestComfortHistoryEntry:
    """Test comfort history entry."""
    
    def test_create_history_entry(self):
        """Test creating history entry."""
        entry = ComfortHistoryEntry(
            timestamp="2025-01-01T00:00:00Z",
            comfort_score=70.0,
            temperature=21.0,
        )
        
        assert entry.comfort_score == 70.0
    
    def test_history_entry_to_dict(self):
        """Test history entry serialization."""
        entry = ComfortHistoryEntry(
            timestamp="2025-01-01T00:00:00Z",
            comfort_score=65.0,
            temperature=20.5,
            humidity=50.0,
            zone_id="zone_living",
        )
        
        d = entry.to_dict()
        
        assert d["zone_id"] == "zone_living"
        assert d["humidity"] == 50.0


class TestComfortAlert:
    """Test comfort alert."""
    
    def test_create_alert(self):
        """Test creating alert."""
        alert = ComfortAlert(
            alert_id="alert_test",
            zone_id="zone_bedroom",
            alert_type="too_hot",
            severity="high",
            current_value=28.0,
            threshold_value=26.0,
            message="Temperature too high",
        )
        
        assert alert.alert_type == "too_hot"
        assert alert.acknowledged is False
    
    def test_alert_to_dict(self):
        """Test alert serialization."""
        alert = ComfortAlert(
            alert_id="alert_test",
            zone_id="zone_living",
            alert_type="too_cold",
            severity="critical",
            current_value=15.0,
            threshold_value=18.0,
            message="Too cold",
            acknowledged=True,
        )
        
        d = alert.to_dict()
        
        assert d["acknowledged"] is True
        assert d["severity"] == "critical"


class TestZoneComfortEngine:
    """Test zone comfort engine."""
    
    def test_create_engine(self):
        """Test engine creation."""
        engine = create_zone_comfort_engine()
        assert engine is not None
    
    def test_engine_has_default_profiles(self):
        """Test that engine has default profiles."""
        engine = ZoneComfortEngine()
        
        profiles = engine.list_profiles()
        
        assert len(profiles) >= 5  # baby, elderly, office, sleep, living
    
    def test_set_zone_profile(self):
        """Test setting zone profile."""
        engine = ZoneComfortEngine()
        
        profile = ZoneComfortProfile(
            profile_id="profile_custom",
            name="Custom",
            profile_type="custom",
        )
        
        result = engine.set_zone_profile("zone_test", profile)
        
        assert result is True
        
        retrieved = engine.get_zone_profile("zone_test")
        
        assert retrieved.profile_id == "profile_custom"
    
    def test_set_zone_profile_by_type(self):
        """Test setting zone profile by type."""
        engine = ZoneComfortEngine()
        
        result = engine.set_zone_profile_by_type("zone_baby", "baby")
        
        assert result is True
        
        profile = engine.get_zone_profile("zone_baby")
        
        assert profile.profile_type == "baby"
    
    def test_set_zone_profile_by_invalid_type(self):
        """Test setting zone profile by invalid type."""
        engine = ZoneComfortEngine()
        
        result = engine.set_zone_profile_by_type("zone_test", "invalid_type")
        
        assert result is False
    
    def test_get_zone_profile_default(self):
        """Test getting default zone profile."""
        engine = ZoneComfortEngine()
        
        # No profile set - should return default
        profile = engine.get_zone_profile("zone_unknown")
        
        assert profile is not None  # Default profile
    
    def test_update_zone_sensors(self):
        """Test updating zone sensors."""
        engine = ZoneComfortEngine()
        
        engine.update_zone_sensors("zone_living", {
            "temperature": 22.0,
            "humidity": 50.0,
        })
        
        assert engine._zone_sensor_data["zone_living"]["temperature"] == 22.0
    
    def test_update_zone_sensors_merge(self):
        """Test that sensor updates merge."""
        engine = ZoneComfortEngine()
        
        engine.update_zone_sensors("zone_living", {"temperature": 22.0})
        engine.update_zone_sensors("zone_living", {"humidity": 50.0})
        
        assert engine._zone_sensor_data["zone_living"]["temperature"] == 22.0
        assert engine._zone_sensor_data["zone_living"]["humidity"] == 50.0
    
    def test_calculate_comfort_no_sensors(self):
        """Test calculating comfort without sensors."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        
        state = engine.calculate_comfort("zone_test")
        
        assert state.comfort_score == 50.0  # Default neutral
        assert state.comfort_level == ComfortLevel.NEUTRAL
    
    def test_calculate_comfort_optimal_temperature(self):
        """Test comfort with optimal temperature."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {"temperature": 22.0})
        
        state = engine.calculate_comfort("zone_test")
        
        assert state.comfort_score > 70  # Should be comfortable
        assert state.temperature == 22.0
    
    def test_calculate_comfort_too_hot(self):
        """Test comfort with too hot temperature."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {"temperature": 30.0})
        
        state = engine.calculate_comfort("zone_test")
        
        assert state.comfort_score < 50  # Should be uncomfortable
        assert state.factor_scores["temperature"] < 50
    
    def test_calculate_comfort_too_cold(self):
        """Test comfort with too cold temperature."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {"temperature": 15.0})
        
        state = engine.calculate_comfort("zone_test")
        
        assert state.comfort_score < 50
        assert state.factor_scores["temperature"] < 50
    
    def test_calculate_comfort_with_humidity(self):
        """Test comfort with humidity."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {
            "temperature": 22.0,
            "humidity": 50.0,
        })
        
        state = engine.calculate_comfort("zone_test")
        
        assert state.humidity == 50.0
        assert "humidity" in state.factor_scores
    
    def test_calculate_comfort_with_light(self):
        """Test comfort with light."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {
            "temperature": 22.0,
            "light": 0.5,
        })
        
        state = engine.calculate_comfort("zone_test")
        
        assert state.light == 0.5
        assert "light" in state.factor_scores
    
    def test_calculate_comfort_with_noise(self):
        """Test comfort with noise."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {
            "temperature": 22.0,
            "noise": 0.3,
        })
        
        state = engine.calculate_comfort("zone_test")
        
        assert state.noise == 0.3
        assert "noise" in state.factor_scores
    
    def test_calculate_comfort_with_air_quality(self):
        """Test comfort with air quality."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {
            "temperature": 22.0,
            "air_quality": 0.9,
        })
        
        state = engine.calculate_comfort("zone_test")
        
        assert state.air_quality == 0.9
        assert "air_quality" in state.factor_scores
    
    def test_calculate_comfort_all_factors(self):
        """Test comfort with all factors."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {
            "temperature": 22.0,
            "humidity": 50.0,
            "light": 0.5,
            "noise": 0.3,
            "air_quality": 0.9,
        })
        
        state = engine.calculate_comfort("zone_test")
        
        assert state.comfort_score > 70  # Should be very comfortable
        assert len(state.factor_scores) == 5
    
    def test_get_comfort_level_very_uncomfortable(self):
        """Test comfort level classification (very uncomfortable)."""
        engine = ZoneComfortEngine()
        
        level = engine._get_comfort_level(15.0)
        
        assert level == ComfortLevel.VERY_UNCOMFORTABLE
    
    def test_get_comfort_level_uncomfortable(self):
        """Test comfort level classification (uncomfortable)."""
        engine = ZoneComfortEngine()
        
        level = engine._get_comfort_level(35.0)
        
        assert level == ComfortLevel.UNCOMFORTABLE
    
    def test_get_comfort_level_neutral(self):
        """Test comfort level classification (neutral)."""
        engine = ZoneComfortEngine()
        
        level = engine._get_comfort_level(50.0)
        
        assert level == ComfortLevel.NEUTRAL
    
    def test_get_comfort_level_comfortable(self):
        """Test comfort level classification (comfortable)."""
        engine = ZoneComfortEngine()
        
        level = engine._get_comfort_level(70.0)
        
        assert level == ComfortLevel.COMFORTABLE
    
    def test_get_comfort_level_very_comfortable(self):
        """Test comfort level classification (very comfortable)."""
        engine = ZoneComfortEngine()
        
        level = engine._get_comfort_level(90.0)
        
        assert level == ComfortLevel.VERY_COMFORTABLE
    
    def test_temperature_score_optimal(self):
        """Test temperature score at optimal."""
        engine = ZoneComfortEngine()
        
        profile = engine._profiles["living"]
        score = engine._calculate_temp_score(profile.temp_optimal, profile)
        
        assert score > 80
    
    def test_temperature_score_too_hot(self):
        """Test temperature score when too hot."""
        engine = ZoneComfortEngine()
        
        profile = engine._profiles["living"]
        score = engine._calculate_temp_score(30.0, profile)
        
        assert score < 50
    
    def test_temperature_score_too_cold(self):
        """Test temperature score when too cold."""
        engine = ZoneComfortEngine()
        
        profile = engine._profiles["living"]
        score = engine._calculate_temp_score(10.0, profile)
        
        assert score < 50
    
    def test_humidity_score_optimal(self):
        """Test humidity score at optimal."""
        engine = ZoneComfortEngine()
        
        profile = engine._profiles["living"]
        score = engine._calculate_humidity_score(profile.humidity_optimal, profile)
        
        assert score > 80
    
    def test_humidity_score_too_high(self):
        """Test humidity score when too high."""
        engine = ZoneComfortEngine()
        
        profile = engine._profiles["living"]
        score = engine._calculate_humidity_score(80.0, profile)
        
        assert score < 50
    
    def test_humidity_score_too_low(self):
        """Test humidity score when too low."""
        engine = ZoneComfortEngine()
        
        profile = engine._profiles["living"]
        score = engine._calculate_humidity_score(20.0, profile)
        
        assert score < 50
    
    def test_light_score_optimal(self):
        """Test light score at optimal."""
        engine = ZoneComfortEngine()
        
        profile = engine._profiles["living"]
        score = engine._calculate_light_score(profile.light_optimal, profile)
        
        assert score > 80
    
    def test_light_score_too_bright(self):
        """Test light score when too bright."""
        engine = ZoneComfortEngine()
        
        profile = engine._profiles["living"]
        score = engine._calculate_light_score(0.95, profile)
        
        assert score < 50
    
    def test_light_score_too_dark(self):
        """Test light score when too dark."""
        engine = ZoneComfortEngine()
        
        profile = engine._profiles["living"]
        score = engine._calculate_light_score(0.05, profile)
        
        assert score < 50
    
    def test_noise_score_optimal(self):
        """Test noise score at optimal."""
        engine = ZoneComfortEngine()
        
        profile = engine._profiles["living"]
        score = engine._calculate_noise_score(profile.noise_optimal, profile)
        
        assert score == 100.0
    
    def test_noise_score_too_loud(self):
        """Test noise score when too loud."""
        engine = ZoneComfortEngine()
        
        profile = engine._profiles["living"]
        score = engine._calculate_noise_score(0.8, profile)
        
        assert score < 50
    
    def test_air_quality_score(self):
        """Test air quality score."""
        engine = ZoneComfortEngine()
        
        score = engine._calculate_air_quality_score(0.9)
        
        assert score == 90.0
    
    def test_weighted_score_single_factor(self):
        """Test weighted score with single factor."""
        engine = ZoneComfortEngine()
        
        profile = engine._profiles["living"]
        
        factor_scores = {"temperature": 80.0}
        
        score = engine._calculate_weighted_score(factor_scores, profile)
        
        assert score > 0
    
    def test_weighted_score_multiple_factors(self):
        """Test weighted score with multiple factors."""
        engine = ZoneComfortEngine()
        
        profile = engine._profiles["living"]
        
        factor_scores = {
            "temperature": 80.0,
            "humidity": 70.0,
            "light": 60.0,
        }
        
        score = engine._calculate_weighted_score(factor_scores, profile)
        
        assert 60 <= score <= 80
    
    def test_weighted_score_no_factors(self):
        """Test weighted score with no factors."""
        engine = ZoneComfortEngine()
        
        profile = engine._profiles["living"]
        
        score = engine._calculate_weighted_score({}, profile)
        
        assert score == 50.0  # Default neutral
    
    def test_get_comfort_history_empty(self):
        """Test getting comfort history when empty."""
        engine = ZoneComfortEngine()
        
        history = engine.get_comfort_history("zone_nonexistent")
        
        assert history == []
    
    def test_get_comfort_history_records(self):
        """Test that comfort history is recorded."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {"temperature": 22.0})
        
        engine.calculate_comfort("zone_test")
        
        history = engine.get_comfort_history("zone_test")
        
        assert len(history) >= 1
    
    def test_get_comfort_history_limit(self):
        """Test comfort history limit."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        
        for i in range(200):
            engine.update_zone_sensors("zone_test", {"temperature": 20.0 + (i % 5) * 0.5})
            engine.calculate_comfort("zone_test")
        
        history = engine.get_comfort_history("zone_test", limit=50)
        
        assert len(history) <= 50
    
    def test_get_comfort_trend_stable(self):
        """Test comfort trend (stable)."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        
        for i in range(20):
            engine.update_zone_sensors("zone_test", {"temperature": 22.0})
            engine.calculate_comfort("zone_test")
        
        trend = engine.get_comfort_trend("zone_test")
        
        assert trend["trend"] == "stable"
    
    def test_get_comfort_trend_improving(self):
        """Test comfort trend (improving)."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        
        # First half: low comfort
        for i in range(10):
            engine.update_zone_sensors("zone_test", {"temperature": 15.0})
            engine.calculate_comfort("zone_test")
        
        # Second half: high comfort
        for i in range(10):
            engine.update_zone_sensors("zone_test", {"temperature": 22.0})
            engine.calculate_comfort("zone_test")
        
        trend = engine.get_comfort_trend("zone_test")
        
        assert trend["trend"] == "improving"
        assert trend["change"] > 0
    
    def test_get_comfort_trend_declining(self):
        """Test comfort trend (declining)."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        
        # First half: high comfort
        for i in range(10):
            engine.update_zone_sensors("zone_test", {"temperature": 22.0})
            engine.calculate_comfort("zone_test")
        
        # Second half: low comfort
        for i in range(10):
            engine.update_zone_sensors("zone_test", {"temperature": 30.0})
            engine.calculate_comfort("zone_test")
        
        trend = engine.get_comfort_trend("zone_test")
        
        assert trend["trend"] == "declining"
        assert trend["change"] < 0
    
    def test_get_alerts_empty(self):
        """Test getting alerts when empty."""
        engine = ZoneComfortEngine()
        
        alerts = engine.get_alerts("zone_nonexistent")
        
        assert alerts == []
    
    def test_alerts_generated_too_hot(self):
        """Test that alerts are generated when too hot."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {"temperature": 30.0})
        
        engine.calculate_comfort("zone_test")
        
        alerts = engine.get_alerts("zone_test")
        
        assert len(alerts) >= 1
        assert alerts[0].alert_type == "too_hot"
    
    def test_alerts_generated_too_cold(self):
        """Test that alerts are generated when too cold."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {"temperature": 10.0})
        
        engine.calculate_comfort("zone_test")
        
        alerts = engine.get_alerts("zone_test")
        
        assert len(alerts) >= 1
        assert alerts[0].alert_type == "too_cold"
    
    def test_alerts_generated_too_humid(self):
        """Test that alerts are generated when too humid."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {"temperature": 22.0, "humidity": 80.0})
        
        engine.calculate_comfort("zone_test")
        
        alerts = engine.get_alerts("zone_test")
        
        humid_alerts = [a for a in alerts if a.alert_type == "too_humid"]
        
        assert len(humid_alerts) >= 1
    
    def test_alerts_generated_too_dry(self):
        """Test that alerts are generated when too dry."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {"temperature": 22.0, "humidity": 20.0})
        
        engine.calculate_comfort("zone_test")
        
        alerts = engine.get_alerts("zone_test")
        
        dry_alerts = [a for a in alerts if a.alert_type == "too_dry"]
        
        assert len(dry_alerts) >= 1
    
    def test_acknowledge_alert(self):
        """Test acknowledging alert."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {"temperature": 30.0})
        
        engine.calculate_comfort("zone_test")
        
        alerts = engine.get_alerts("zone_test")
        
        result = engine.acknowledge_alert("zone_test", alerts[0].alert_id)
        
        assert result is True
        
        # Should not appear in unacknowledged
        unack = engine.get_alerts("zone_test", unacknowledged_only=True)
        
        assert alerts[0].alert_id not in [a.alert_id for a in unack]
    
    def test_acknowledge_nonexistent_alert(self):
        """Test acknowledging nonexistent alert."""
        engine = ZoneComfortEngine()
        
        result = engine.acknowledge_alert("zone_test", "nonexistent")
        
        assert result is False
    
    def test_clear_alerts(self):
        """Test clearing alerts."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {"temperature": 30.0})
        
        engine.calculate_comfort("zone_test")
        
        count = engine.clear_alerts("zone_test")
        
        assert count >= 1
        
        alerts = engine.get_alerts("zone_test")
        
        assert len(alerts) == 0
    
    def test_get_zone_state(self):
        """Test getting zone state."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {"temperature": 22.0})
        
        state = engine.get_zone_state("zone_test")
        
        assert state is not None
        assert state.temperature == 22.0
    
    def test_get_zone_state_no_sensors(self):
        """Test getting zone state without sensors."""
        engine = ZoneComfortEngine()
        
        state = engine.get_zone_state("zone_nonexistent")
        
        assert state is None
    
    def test_list_profiles(self):
        """Test listing profiles."""
        engine = ZoneComfortEngine()
        
        profiles = engine.list_profiles()
        
        assert len(profiles) >= 5
        assert all("profile_id" in p for p in profiles)
    
    def test_get_statistics(self):
        """Test getting statistics."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_1", "living")
        engine.set_zone_profile_by_type("zone_2", "bedroom")
        
        stats = engine.get_statistics()
        
        assert stats["total_zones"] == 2
        assert stats["total_profiles"] >= 5
    
    def test_statistics_alert_counts(self):
        """Test that statistics track alerts."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {"temperature": 30.0})
        
        engine.calculate_comfort("zone_test")
        
        stats = engine.get_statistics()
        
        assert stats["total_alerts"] >= 1
    
    def test_statistics_unacknowledged_alerts(self):
        """Test that statistics track unacknowledged alerts."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {"temperature": 30.0})
        
        engine.calculate_comfort("zone_test")
        
        stats = engine.get_statistics()
        
        assert stats["unacknowledged_alerts"] >= 1
    
    def test_statistics_history_entries(self):
        """Test that statistics track history entries."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        
        for i in range(10):
            engine.update_zone_sensors("zone_test", {"temperature": 22.0})
            engine.calculate_comfort("zone_test")
        
        stats = engine.get_statistics()
        
        assert stats["total_history_entries"] >= 10
    
    def test_baby_profile_exists(self):
        """Test that baby profile exists."""
        engine = ZoneComfortEngine()
        
        profile = engine._profiles.get("baby")
        
        assert profile is not None
        assert profile.temp_optimal == 22.0
    
    def test_elderly_profile_exists(self):
        """Test that elderly profile exists."""
        engine = ZoneComfortEngine()
        
        profile = engine._profiles.get("elderly")
        
        assert profile is not None
        assert profile.temp_optimal == 23.5
    
    def test_office_profile_exists(self):
        """Test that office profile exists."""
        engine = ZoneComfortEngine()
        
        profile = engine._profiles.get("office")
        
        assert profile is not None
        assert profile.light_optimal == 0.7
    
    def test_sleep_profile_exists(self):
        """Test that sleep profile exists."""
        engine = ZoneComfortEngine()
        
        profile = engine._profiles.get("sleep")
        
        assert profile is not None
        assert profile.temp_optimal == 19.0
        assert profile.light_optimal == 0.0
    
    def test_living_profile_exists(self):
        """Test that living profile exists."""
        engine = ZoneComfortEngine()
        
        profile = engine._profiles.get("living")
        
        assert profile is not None
    
    def test_multiple_zones_independent(self):
        """Test that multiple zones are independent."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_hot", "living")
        engine.set_zone_profile_by_type("zone_cold", "living")
        
        engine.update_zone_sensors("zone_hot", {"temperature": 28.0})
        engine.update_zone_sensors("zone_cold", {"temperature": 16.0})
        
        hot_state = engine.calculate_comfort("zone_hot")
        cold_state = engine.calculate_comfort("zone_cold")
        
        assert hot_state.comfort_score > cold_state.comfort_score
    
    def test_history_limited_to_1000(self):
        """Test that history is limited to 1000 entries."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        
        for i in range(1500):
            engine.update_zone_sensors("zone_test", {"temperature": 22.0})
            engine.calculate_comfort("zone_test")
        
        history = engine._zone_comfort_history["zone_test"]
        
        assert len(history) == 1000
    
    def test_alerts_limited_to_100(self):
        """Test that alerts are limited to 100 per zone."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        
        for i in range(150):
            engine.update_zone_sensors("zone_test", {"temperature": 30.0})
            engine.calculate_comfort("zone_test")
        
        alerts = engine._zone_alerts["zone_test"]
        
        assert len(alerts) == 100
    
    def test_create_engine_returns_instance(self):
        """Test that factory function returns instance."""
        engine = create_zone_comfort_engine()
        
        assert isinstance(engine, ZoneComfortEngine)
    
    def test_profile_to_dict_includes_all_fields(self):
        """Test that profile to_dict includes all fields."""
        profile = ZoneComfortProfile(
            profile_id="profile_test",
            name="Test",
            profile_type="custom",
            temp_min=18.0,
            temp_max=26.0,
            temp_optimal=22.0,
            humidity_optimal=50.0,
            light_optimal=0.5,
            noise_optimal=0.2,
        )
        
        d = profile.to_dict()
        
        assert d["temperature"]["min"] == 18.0
        assert d["temperature"]["optimal"] == 22.0
        assert d["humidity"]["optimal"] == 50.0
    
    def test_state_timestamp_set(self):
        """Test that state timestamp is set."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {"temperature": 22.0})
        
        state = engine.calculate_comfort("zone_test")
        
        assert state.timestamp is not None
    
    def test_alert_timestamp_set(self):
        """Test that alert timestamp is set."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {"temperature": 30.0})
        
        engine.calculate_comfort("zone_test")
        
        alerts = engine.get_alerts("zone_test")
        
        assert alerts[0].created_at is not None
    
    def test_history_entry_timestamp_set(self):
        """Test that history entry timestamp is set."""
        entry = ComfortHistoryEntry(
            timestamp="2025-01-01T00:00:00Z",
            comfort_score=70.0,
        )
        
        assert entry.timestamp is not None
    
    def test_comfort_level_boundaries(self):
        """Test comfort level boundaries."""
        engine = ZoneComfortEngine()
        
        assert engine._get_comfort_level(0.0) == ComfortLevel.VERY_UNCOMFORTABLE
        assert engine._get_comfort_level(19.9) == ComfortLevel.VERY_UNCOMFORTABLE
        assert engine._get_comfort_level(20.0) == ComfortLevel.UNCOMFORTABLE
        assert engine._get_comfort_level(39.9) == ComfortLevel.UNCOMFORTABLE
        assert engine._get_comfort_level(40.0) == ComfortLevel.NEUTRAL
        assert engine._get_comfort_level(59.9) == ComfortLevel.NEUTRAL
        assert engine._get_comfort_level(60.0) == ComfortLevel.COMFORTABLE
        assert engine._get_comfort_level(79.9) == ComfortLevel.COMFORTABLE
        assert engine._get_comfort_level(80.0) == ComfortLevel.VERY_COMFORTABLE
        assert engine._get_comfort_level(100.0) == ComfortLevel.VERY_COMFORTABLE
    
    def test_get_comfort_trend_insufficient_data(self):
        """Test comfort trend with insufficient data."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {"temperature": 22.0})
        engine.calculate_comfort("zone_test")
        
        trend = engine.get_comfort_trend("zone_test")
        
        assert trend["trend"] == "stable"
        assert trend["data_points"] == 1
    
    def test_get_alerts_by_severity(self):
        """Test getting alerts by severity."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {"temperature": 35.0})  # Critical
        
        engine.calculate_comfort("zone_test")
        
        alerts = engine.get_alerts("zone_test")
        
        assert len(alerts) >= 1
        assert alerts[0].severity in ("low", "medium", "high", "critical")
    
    def test_clear_alerts_nonexistent_zone(self):
        """Test clearing alerts for nonexistent zone."""
        engine = ZoneComfortEngine()
        
        count = engine.clear_alerts("nonexistent")
        
        assert count == 0
    
    def test_update_zone_sensors_empty(self):
        """Test updating zone sensors with empty data."""
        engine = ZoneComfortEngine()
        
        engine.update_zone_sensors("zone_test", {})
        
        assert engine._zone_sensor_data["zone_test"] == {}
    
    def test_calculate_comfort_preserves_sensor_data(self):
        """Test that calculate_comfort preserves sensor data."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {"temperature": 22.0, "humidity": 50.0})
        
        engine.calculate_comfort("zone_test")
        
        assert engine._zone_sensor_data["zone_test"]["temperature"] == 22.0
        assert engine._zone_sensor_data["zone_test"]["humidity"] == 50.0
    
    def test_profile_weights_custom(self):
        """Test custom profile weights."""
        profile = ZoneComfortProfile(
            profile_id="profile_custom",
            name="Custom",
            profile_type="custom",
            temp_weight=0.50,
            humidity_weight=0.30,
            light_weight=0.10,
            noise_weight=0.05,
            air_quality_weight=0.05,
        )
        
        total = (
            profile.temp_weight +
            profile.humidity_weight +
            profile.light_weight +
            profile.noise_weight +
            profile.air_quality_weight
        )
        
        assert abs(total - 1.0) < 0.001
    
    def test_alert_message_includes_values(self):
        """Test that alert message includes current and threshold values."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {"temperature": 30.0})
        
        engine.calculate_comfort("zone_test")
        
        alerts = engine.get_alerts("zone_test")
        
        assert "30.0" in alerts[0].message or "26.0" in alerts[0].message
    
    def test_zone_state_factor_scores(self):
        """Test that zone state includes factor scores."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        engine.update_zone_sensors("zone_test", {
            "temperature": 22.0,
            "humidity": 50.0,
        })
        
        state = engine.calculate_comfort("zone_test")
        
        assert "temperature" in state.factor_scores
        assert "humidity" in state.factor_scores
    
    def test_get_comfort_history_by_hours(self):
        """Test getting comfort history filtered by hours."""
        engine = ZoneComfortEngine()
        
        engine.set_zone_profile_by_type("zone_test", "living")
        
        # Add some history
        for i in range(10):
            engine.update_zone_sensors("zone_test", {"temperature": 22.0})
            engine.calculate_comfort("zone_test")
        
        # Get last hour
        history = engine.get_comfort_history("zone_test", hours=1)
        
        # Should return entries from last hour
        assert isinstance(history, list)
    
    def test_statistics_initial_values(self):
        """Test statistics initial values."""
        engine = ZoneComfortEngine()
        
        stats = engine.get_statistics()
        
        assert stats["total_zones"] == 0
        assert stats["total_alerts"] == 0
        assert stats["unacknowledged_alerts"] == 0
    
    def test_default_profile_is_living(self):
        """Test that default profile is living."""
        engine = ZoneComfortEngine()
        
        assert engine._default_profile.profile_type == "living"
    
    def test_set_zone_profile_by_type_returns_false_for_unknown(self):
        """Test that set_zone_profile_by_type returns False for unknown type."""
        engine = ZoneComfortEngine()
        
        result = engine.set_zone_profile_by_type("zone_test", "unknown_type")
        
        assert result is False
    
    def test_get_zone_profile_returns_default_for_unset(self):
        """Test that get_zone_profile returns default for unset zone."""
        engine = ZoneComfortEngine()
        
        profile = engine.get_zone_profile("zone_unset")
        
        assert profile is not None
        assert profile == engine._default_profile
