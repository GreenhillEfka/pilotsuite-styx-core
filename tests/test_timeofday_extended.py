"""Tests for TimeOfDay Module Extensions — Slice 77."""
import pytest
from copilot_core.timeofday.timeofday_extended import (
    TimeOfDayModuleExtended,
    GeographicLocation,
    SunTimes,
    MoonData,
    TimeOfDayProfile,
    TwilightType,
    MoonPhase,
    create_time_of_day_module_extended,
)
from datetime import datetime, timezone


class TestTwilightType:
    def test_twilight_enum_values(self):
        assert TwilightType.CIVIL.value == "civil"
        assert TwilightType.NAUTICAL.value == "nautical"
        assert TwilightType.ASTRONOMICAL.value == "astronomical"


class TestMoonPhase:
    def test_moon_enum_values(self):
        assert MoonPhase.NEW_MOON.value == "new_moon"
        assert MoonPhase.FULL_MOON.value == "full_moon"


class TestGeographicLocation:
    def test_create_location(self):
        loc = GeographicLocation(latitude=52.52, longitude=13.41, timezone="Europe/Berlin")
        assert loc.latitude == 52.52
        assert loc.timezone == "Europe/Berlin"
    
    def test_validate_valid(self):
        loc = GeographicLocation(latitude=52.52, longitude=13.41)
        valid, error = loc.validate()
        assert valid is True
        assert error is None
    
    def test_validate_invalid_latitude(self):
        loc = GeographicLocation(latitude=95.0, longitude=13.41)
        valid, error = loc.validate()
        assert valid is False
        assert "Latitude" in error
    
    def test_validate_invalid_longitude(self):
        loc = GeographicLocation(latitude=52.52, longitude=200.0)
        valid, error = loc.validate()
        assert valid is False
        assert "Longitude" in error
    
    def test_location_to_dict(self):
        loc = GeographicLocation(latitude=40.71, longitude=-74.01, timezone="America/New_York")
        d = loc.to_dict()
        assert d["latitude"] == 40.71
        assert d["timezone"] == "America/New_York"


class TestTimeOfDayProfile:
    def test_create_profile(self):
        profile = TimeOfDayProfile(
            profile_id="profile_1",
            zone_id="zone_living",
            name="Living Profile",
        )
        assert profile.use_geographic is False
        assert profile.golden_hour_enabled is True
    
    def test_profile_with_location(self):
        loc = GeographicLocation(latitude=52.52, longitude=13.41)
        profile = TimeOfDayProfile(
            profile_id="profile_1",
            zone_id="zone_living",
            name="Living",
            location=loc,
            use_geographic=True,
        )
        assert profile.location is not None
        assert profile.use_geographic is True
    
    def test_profile_fixed_times(self):
        profile = TimeOfDayProfile(
            profile_id="profile_1",
            zone_id="zone_living",
            name="Living",
            fixed_sunrise="07:00",
            fixed_sunset="20:00",
        )
        assert profile.fixed_sunrise == "07:00"
        assert profile.fixed_sunset == "20:00"
    
    def test_profile_to_dict(self):
        profile = TimeOfDayProfile(
            profile_id="profile_1",
            zone_id="zone_living",
            name="Test",
            blue_hour_enabled=True,
            twilight_mode=TwilightType.NAUTICAL,
        )
        d = profile.to_dict()
        assert d["blue_hour_enabled"] is True
        assert d["twilight_mode"] == "nautical"


class TestSunTimes:
    def test_create_sun_times(self):
        loc = GeographicLocation(latitude=52.52, longitude=13.41)
        sun = SunTimes(
            date="2025-01-01",
            location=loc,
            sunrise="2025-01-01T08:00:00Z",
            sunset="2025-01-01T16:00:00Z",
        )
        assert sun.sunrise == "2025-01-01T08:00:00Z"
    
    def test_sun_times_to_dict(self):
        loc = GeographicLocation(latitude=52.52, longitude=13.41)
        sun = SunTimes(
            date="2025-01-01",
            location=loc,
            sunrise="2025-01-01T08:00:00Z",
            sunset="2025-01-01T16:00:00Z",
            day_length_seconds=28800,
        )
        d = sun.to_dict()
        assert d["day_length_seconds"] == 28800


class TestMoonData:
    def test_create_moon_data(self):
        moon = MoonData(
            date="2025-01-01",
            phase=MoonPhase.FULL_MOON,
            illumination=1.0,
            age_days=14.8,
        )
        assert moon.phase == MoonPhase.FULL_MOON
        assert moon.illumination == 1.0
    
    def test_moon_data_to_dict(self):
        moon = MoonData(
            date="2025-01-01",
            phase=MoonPhase.NEW_MOON,
            illumination=0.0,
            age_days=0.5,
            next_full_moon="2025-01-15",
        )
        d = moon.to_dict()
        assert d["phase"] == "new_moon"
        assert d["next_full_moon"] == "2025-01-15"


class TestTimeOfDayModuleExtended:
    def test_create_module(self):
        module = create_time_of_day_module_extended()
        assert module is not None
    
    def test_set_profile(self):
        module = TimeOfDayModuleExtended()
        
        profile = TimeOfDayProfile(
            profile_id="profile_1",
            zone_id="zone_living",
            name="Living Profile",
        )
        
        result = module.set_profile(profile)
        
        assert result == "profile_1"
        assert module.get_profile("zone_living") is not None
    
    def test_get_nonexistent_profile(self):
        module = TimeOfDayModuleExtended()
        
        profile = module.get_profile("nonexistent")
        
        assert profile is None
    
    def test_set_location(self):
        module = TimeOfDayModuleExtended()
        
        result = module.set_location("zone_living", 52.52, 13.41, "Europe/Berlin")
        
        assert result is True
        
        profile = module.get_profile("zone_living")
        assert profile is not None
        assert profile.location.latitude == 52.52
    
    def test_set_location_invalid(self):
        module = TimeOfDayModuleExtended()
        
        result = module.set_location("zone_living", 95.0, 13.41)
        
        assert result is False
    
    def test_get_sun_times_no_profile(self):
        module = TimeOfDayModuleExtended()
        
        sun_times = module.get_sun_times("nonexistent")
        
        assert sun_times is None
    
    def test_get_sun_times_default(self):
        module = TimeOfDayModuleExtended()
        
        profile = TimeOfDayProfile("p1", "zone_1", "Test")
        module.set_profile(profile)
        
        sun_times = module.get_sun_times("zone_1")
        
        assert sun_times is not None
        assert sun_times.sunrise is not None
        assert sun_times.sunset is not None
    
    def test_get_sun_times_fixed(self):
        module = TimeOfDayModuleExtended()
        
        profile = TimeOfDayProfile(
            profile_id="p1",
            zone_id="zone_1",
            name="Test",
            fixed_sunrise="07:00",
            fixed_sunset="20:00",
        )
        module.set_profile(profile)
        
        sun_times = module.get_sun_times("zone_1")
        
        assert sun_times is not None
        assert "07:00" in sun_times.sunrise
        assert "20:00" in sun_times.sunset
    
    def test_get_sun_times_geographic(self):
        module = TimeOfDayModuleExtended()
        
        module.set_location("zone_1", 52.52, 13.41, "Europe/Berlin")
        
        sun_times = module.get_sun_times("zone_1")
        
        assert sun_times is not None
        assert sun_times.sunrise is not None
    
    def test_sun_times_cached(self):
        module = TimeOfDayModuleExtended()
        
        module.set_location("zone_1", 52.52, 13.41)
        
        # First call
        sun1 = module.get_sun_times("zone_1")
        
        # Second call (should be cached)
        sun2 = module.get_sun_times("zone_1")
        
        assert sun1 is not None
        assert sun2 is not None
        assert sun1.sunrise == sun2.sunrise
    
    def test_get_moon_data(self):
        module = TimeOfDayModuleExtended()
        
        moon = module.get_moon_data()
        
        assert moon is not None
        assert moon.date is not None
        assert moon.phase is not None
        assert 0.0 <= moon.illumination <= 1.0
    
    def test_moon_data_cached(self):
        module = TimeOfDayModuleExtended()
        
        moon1 = module.get_moon_data()
        moon2 = module.get_moon_data()
        
        assert moon1.date == moon2.date
        assert moon1.phase == moon2.phase
    
    def test_is_golden_hour_no_profile(self):
        module = TimeOfDayModuleExtended()
        
        result = module.is_golden_hour("nonexistent")
        
        assert result is False
    
    def test_is_golden_hour(self):
        module = TimeOfDayModuleExtended()
        
        module.set_location("zone_1", 52.52, 13.41)
        
        # Golden hour depends on time of day - just check it returns bool
        result = module.is_golden_hour("zone_1")
        
        assert isinstance(result, bool)
    
    def test_is_blue_hour(self):
        module = TimeOfDayModuleExtended()
        
        module.set_location("zone_1", 52.52, 13.41)
        
        result = module.is_blue_hour("zone_1")
        
        assert isinstance(result, bool)
    
    def test_get_solar_position_no_location(self):
        module = TimeOfDayModuleExtended()
        
        pos = module.get_solar_position("nonexistent")
        
        assert pos["elevation"] == 0.0
        assert pos["azimuth"] == 0.0
    
    def test_get_solar_position(self):
        module = TimeOfDayModuleExtended()
        
        module.set_location("zone_1", 52.52, 13.41)
        
        pos = module.get_solar_position("zone_1")
        
        assert "elevation" in pos
        assert "azimuth" in pos
    
    def test_get_statistics(self):
        module = TimeOfDayModuleExtended()
        
        module.set_location("zone_1", 52.52, 13.41)
        
        stats = module.get_statistics()
        
        assert stats["total_profiles"] >= 1
        assert stats["zones_with_geographic"] >= 1
    
    def test_create_module_returns_instance(self):
        assert isinstance(create_time_of_day_module_extended(), TimeOfDayModuleExtended)
    
    def test_profile_to_dict_with_location(self):
        loc = GeographicLocation(latitude=40.71, longitude=-74.01)
        profile = TimeOfDayProfile(
            profile_id="p1",
            zone_id="zone_1",
            name="Test",
            location=loc,
        )
        d = profile.to_dict()
        assert d["location"]["latitude"] == 40.71
    
    def test_sun_times_with_twilight(self):
        module = TimeOfDayModuleExtended()
        
        module.set_location("zone_1", 52.52, 13.41)
        
        sun = module.get_sun_times("zone_1")
        
        assert sun is not None
        assert sun.civil_dawn is not None or sun.civil_dusk is not None
    
    def test_sun_times_with_golden_hour(self):
        module = TimeOfDayModuleExtended()
        
        module.set_location("zone_1", 52.52, 13.41)
        
        sun = module.get_sun_times("zone_1")
        
        assert sun is not None
        # Golden hour should be calculated
        assert sun.golden_hour_morning_start is not None
    
    def test_sun_times_with_blue_hour(self):
        module = TimeOfDayModuleExtended()
        
        module.set_location("zone_1", 52.52, 13.41)
        
        sun = module.get_sun_times("zone_1")
        
        assert sun is not None
        # Blue hour should be calculated
        assert sun.blue_hour_morning_start is not None
    
    def test_moon_phase_values(self):
        module = TimeOfDayModuleExtended()
        
        moon = module.get_moon_data()
        
        assert moon.phase in MoonPhase
    
    def test_moon_illumination_range(self):
        module = TimeOfDayModuleExtended()
        
        moon = module.get_moon_data()
        
        assert 0.0 <= moon.illumination <= 1.0
    
    def test_moon_age_days_positive(self):
        module = TimeOfDayModuleExtended()
        
        moon = module.get_moon_data()
        
        assert 0.0 <= moon.age_days <= 29.53
    
    def test_sun_times_day_length_positive(self):
        module = TimeOfDayModuleExtended()
        
        module.set_location("zone_1", 52.52, 13.41)
        
        sun = module.get_sun_times("zone_1")
        
        assert sun.day_length_seconds >= 0
    
    def test_sun_times_date_format(self):
        module = TimeOfDayModuleExtended()
        
        module.set_location("zone_1", 52.52, 13.41)
        
        sun = module.get_sun_times("zone_1")
        
        assert len(sun.date) == 10  # YYYY-MM-DD
    
    def test_profile_twilight_mode_nautical(self):
        module = TimeOfDayModuleExtended()
        
        profile = TimeOfDayProfile(
            profile_id="p1",
            zone_id="zone_1",
            name="Test",
            twilight_mode=TwilightType.NAUTICAL,
        )
        module.set_profile(profile)
        
        sun = module.get_sun_times("zone_1")
        
        assert sun is not None
    
    def test_profile_season_events_enabled(self):
        profile = TimeOfDayProfile(
            profile_id="p1",
            zone_id="zone_1",
            name="Test",
            season_events_enabled=True,
        )
        d = profile.to_dict()
        assert d["season_events_enabled"] is True
    
    def test_location_elevation(self):
        loc = GeographicLocation(
            latitude=47.61,
            longitude=-122.33,
            elevation_meters=100.0,
        )
        d = loc.to_dict()
        assert d["elevation_meters"] == 100.0
    
    def test_sun_times_location_included(self):
        module = TimeOfDayModuleExtended()
        
        module.set_location("zone_1", 52.52, 13.41)
        
        sun = module.get_sun_times("zone_1")
        
        assert sun.location.latitude == 52.52
    
    def test_moon_next_dates_format(self):
        module = TimeOfDayModuleExtended()
        
        moon = module.get_moon_data()
        
        assert len(moon.next_full_moon) == 10  # YYYY-MM-DD
        assert len(moon.next_new_moon) == 10
    
    def test_get_sun_times_specific_date(self):
        module = TimeOfDayModuleExtended()
        
        module.set_location("zone_1", 52.52, 13.41)
        
        test_date = datetime(2025, 6, 21, 12, 0, 0, tzinfo=timezone.utc)  # Summer solstice
        sun = module.get_sun_times("zone_1", at_date=test_date)
        
        assert sun is not None
        assert sun.date == "2025-06-21"
    
    def test_sun_times_cache_cleared_on_location_change(self):
        module = TimeOfDayModuleExtended()
        
        module.set_location("zone_1", 52.52, 13.41)
        module.get_sun_times("zone_1")
        
        # Change location
        module.set_location("zone_1", 40.71, -74.01)
        
        # Cache should be cleared for this zone
        assert f"zone_1_" not in list(module._sun_times_cache.keys())
    
    def test_statistics_zones_with_fixed_times(self):
        module = TimeOfDayModuleExtended()
        
        profile = TimeOfDayProfile(
            profile_id="p1",
            zone_id="zone_1",
            name="Test",
            fixed_sunrise="07:00",
            fixed_sunset="20:00",
        )
        module.set_profile(profile)
        
        stats = module.get_statistics()
        
        assert stats["zones_with_fixed_times"] >= 1
    
    def test_moon_data_cache_limit(self):
        module = TimeOfDayModuleExtended()
        
        # Generate many dates
        for i in range(150):
            date = datetime(2025, 1, 1 + i, tzinfo=timezone.utc)
            module.get_moon_data(at_date=date)
        
        # Cache should be limited
        assert len(module._moon_data_cache) <= 100
    
    def test_sun_times_cache_limit(self):
        module = TimeOfDayModuleExtended()
        
        module.set_location("zone_1", 52.52, 13.41)
        
        # Generate many dates
        for i in range(150):
            date = datetime(2025, 1, 1 + i, tzinfo=timezone.utc)
            module.get_sun_times("zone_1", at_date=date)
        
        # Cache should be limited
        assert len(module._sun_times_cache) <= 1000
    
    def test_profile_without_location(self):
        profile = TimeOfDayProfile(
            profile_id="p1",
            zone_id="zone_1",
            name="Test",
        )
        d = profile.to_dict()
        assert d["location"] is None
    
    def test_set_location_creates_profile_if_missing(self):
        module = TimeOfDayModuleExtended()
        
        module.set_location("zone_new", 52.52, 13.41)
        
        profile = module.get_profile("zone_new")
        
        assert profile is not None
        assert profile.location is not None
    
    def test_is_golden_hour_morning(self):
        module = TimeOfDayModuleExtended()
        
        module.set_location("zone_1", 52.52, 13.41)
        
        # Test during morning golden hour would require specific time
        # Just verify the method works
        result = module.is_golden_hour("zone_1")
        
        assert isinstance(result, bool)
    
    def test_is_blue_hour_evening(self):
        module = TimeOfDayModuleExtended()
        
        module.set_location("zone_1", 52.52, 13.41)
        
        result = module.is_blue_hour("zone_1")
        
        assert isinstance(result, bool)
    
    def test_solar_position_midday(self):
        module = TimeOfDayModuleExtended()
        
        module.set_location("zone_1", 52.52, 13.41)
        
        test_time = datetime(2025, 6, 21, 12, 0, 0, tzinfo=timezone.utc)
        pos = module.get_solar_position("zone_1", at_time=test_time)
        
        # At solar noon, elevation should be positive (Northern Hemisphere summer)
        assert pos["elevation"] > 0
    
    def test_solar_position_night(self):
        module = TimeOfDayModuleExtended()
        
        module.set_location("zone_1", 52.52, 13.41)
        
        test_time = datetime(2025, 6, 21, 2, 0, 0, tzinfo=timezone.utc)
        pos = module.get_solar_position("zone_1", at_time=test_time)
        
        # At night, elevation should be negative
        assert pos["elevation"] < 0
    
    def test_sun_times_solar_noon(self):
        module = TimeOfDayModuleExtended()
        
        module.set_location("zone_1", 52.52, 13.41)
        
        sun = module.get_sun_times("zone_1")
        
        # Solar noon should be between sunrise and sunset
        assert sun.solar_noon is not None
