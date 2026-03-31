"""Tests for Time of Day Module — Slice 72."""
import pytest
from copilot_core.timeofday.zone_time import (
    TimeOfDayModule,
    TimeProfile,
    TimeContext,
    TimeEvent,
    TimeHistoryEntry,
    TimeOfDayPhase,
    Season,
    create_time_of_day_module,
)
from datetime import datetime, timezone, timedelta


class TestTimeOfDayPhase:
    def test_phase_enum_values(self):
        assert TimeOfDayPhase.NIGHT.value == "night"
        assert TimeOfDayPhase.DAWN.value == "dawn"
        assert TimeOfDayPhase.MORNING.value == "morning"
        assert TimeOfDayPhase.AFTERNOON.value == "afternoon"
        assert TimeOfDayPhase.EVENING.value == "evening"
        assert TimeOfDayPhase.LATE_NIGHT.value == "late_night"


class TestSeason:
    def test_season_enum_values(self):
        assert Season.SPRING.value == "spring"
        assert Season.SUMMER.value == "summer"
        assert Season.AUTUMN.value == "autumn"
        assert Season.WINTER.value == "winter"


class TestTimeProfile:
    def test_create_profile(self):
        profile = TimeProfile(profile_id="profile_test", name="Test Profile", zone_id="zone_living")
        assert profile.profile_id == "profile_test"
        assert profile.night_start == 22
    
    def test_profile_to_dict(self):
        profile = TimeProfile(profile_id="p1", name="Test", zone_id="zone_test", night_start=20)
        d = profile.to_dict()
        assert d["night_start"] == 20


class TestTimeContext:
    def test_create_context(self):
        context = TimeContext(
            timestamp="2025-01-01T12:00:00Z", hour=12, minute=0, day_of_week=0,
            is_weekend=False, is_holiday=False, phase=TimeOfDayPhase.AFTERNOON,
            season=Season.WINTER, daylight_factor=0.9, sunset_factor=1.0,
        )
        assert context.hour == 12
        assert context.phase == TimeOfDayPhase.AFTERNOON
    
    def test_context_to_dict(self):
        context = TimeContext(
            timestamp="2025-01-01T12:00:00Z", hour=12, minute=0, day_of_week=0,
            is_weekend=False, is_holiday=False, phase=TimeOfDayPhase.MORNING,
            season=Season.SPRING, daylight_factor=0.7, sunset_factor=0.8,
        )
        d = context.to_dict()
        assert d["phase"] == "morning"


class TestTimeEvent:
    def test_create_event(self):
        event = TimeEvent(
            event_id="tevt_test", zone_id="zone_living", event_type="phase_change",
            from_value="morning", to_value="afternoon",
        )
        assert event.event_type == "phase_change"
    
    def test_event_to_dict(self):
        event = TimeEvent(
            event_id="tevt_test", zone_id="zone_living", event_type="phase_change",
            from_value="evening", to_value="night",
        )
        d = event.to_dict()
        assert d["from_value"] == "evening"


class TestTimeHistoryEntry:
    def test_create_history_entry(self):
        entry = TimeHistoryEntry(
            timestamp="2025-01-01T12:00:00Z", zone_id="zone_living",
            phase=TimeOfDayPhase.AFTERNOON, is_weekend=False, is_holiday=False,
        )
        assert entry.phase == TimeOfDayPhase.AFTERNOON
    
    def test_history_entry_to_dict(self):
        entry = TimeHistoryEntry(
            timestamp="2025-01-01T12:00:00Z", zone_id="zone_bedroom",
            phase=TimeOfDayPhase.NIGHT, is_weekend=True, is_holiday=False,
        )
        d = entry.to_dict()
        assert d["is_weekend"] is True


class TestTimeOfDayModule:
    def test_create_module(self):
        module = create_time_of_day_module()
        assert module is not None
    
    def test_set_zone_profile(self):
        module = TimeOfDayModule()
        profile = TimeProfile(profile_id="p1", name="Test", zone_id="zone_living")
        result = module.set_zone_profile("zone_living", profile)
        assert result is True
        assert module.get_zone_profile("zone_living").name == "Test"
    
    def test_get_zone_profile_nonexistent(self):
        module = TimeOfDayModule()
        assert module.get_zone_profile("nonexistent") is None
    
    def test_set_holiday_dates(self):
        module = TimeOfDayModule()
        module.set_holiday_dates(["2025-01-01", "2025-12-25"])
        assert "2025-01-01" in module._holiday_dates
    
    def test_add_holiday_date(self):
        module = TimeOfDayModule()
        module.add_holiday_date("2025-01-01")
        assert "2025-01-01" in module._holiday_dates
    
    def test_remove_holiday_date(self):
        module = TimeOfDayModule()
        module.add_holiday_date("2025-01-01")
        assert module.remove_holiday_date("2025-01-01") is True
        assert "2025-01-01" not in module._holiday_dates
    
    def test_get_time_context(self):
        module = TimeOfDayModule()
        profile = TimeProfile("p1", "Test", "zone_living")
        module.set_zone_profile("zone_living", profile)
        context = module.get_time_context("zone_living")
        assert context is not None
    
    def test_phase_calculation_night(self):
        module = TimeOfDayModule()
        test_time = datetime(2025, 1, 1, 23, 0, 0, tzinfo=timezone.utc)
        profile = TimeProfile("p1", "Test", "zone_living")
        phase = module._calculate_phase(test_time, profile)
        assert phase == TimeOfDayPhase.NIGHT
    
    def test_phase_calculation_morning(self):
        module = TimeOfDayModule()
        test_time = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        profile = TimeProfile("p1", "Test", "zone_living")
        phase = module._calculate_phase(test_time, profile)
        assert phase == TimeOfDayPhase.MORNING
    
    def test_phase_calculation_afternoon(self):
        module = TimeOfDayModule()
        test_time = datetime(2025, 1, 1, 14, 0, 0, tzinfo=timezone.utc)
        profile = TimeProfile("p1", "Test", "zone_living")
        phase = module._calculate_phase(test_time, profile)
        assert phase == TimeOfDayPhase.AFTERNOON
    
    def test_phase_calculation_evening(self):
        module = TimeOfDayModule()
        test_time = datetime(2025, 1, 1, 19, 0, 0, tzinfo=timezone.utc)
        profile = TimeProfile("p1", "Test", "zone_living")
        phase = module._calculate_phase(test_time, profile)
        assert phase == TimeOfDayPhase.EVENING
    
    def test_season_calculation_spring(self):
        module = TimeOfDayModule()
        test_time = datetime(2025, 4, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert module._calculate_season(test_time) == Season.SPRING
    
    def test_season_calculation_summer(self):
        module = TimeOfDayModule()
        test_time = datetime(2025, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert module._calculate_season(test_time) == Season.SUMMER
    
    def test_season_calculation_autumn(self):
        module = TimeOfDayModule()
        test_time = datetime(2025, 10, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert module._calculate_season(test_time) == Season.AUTUMN
    
    def test_season_calculation_winter(self):
        module = TimeOfDayModule()
        test_time = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        assert module._calculate_season(test_time) == Season.WINTER
    
    def test_is_night(self):
        module = TimeOfDayModule()
        profile = TimeProfile("p1", "Test", "zone_living")
        module.set_zone_profile("zone_living", profile)
        test_time = datetime(2025, 1, 1, 23, 0, 0, tzinfo=timezone.utc)
        module.get_time_context("zone_living", at_time=test_time)
        assert module.is_night("zone_living") is True
    
    def test_is_day(self):
        module = TimeOfDayModule()
        profile = TimeProfile("p1", "Test", "zone_living")
        module.set_zone_profile("zone_living", profile)
        test_time = datetime(2025, 1, 1, 14, 0, 0, tzinfo=timezone.utc)
        module.get_time_context("zone_living", at_time=test_time)
        assert module.is_day("zone_living") is True
    
    def test_is_evening(self):
        module = TimeOfDayModule()
        profile = TimeProfile("p1", "Test", "zone_living")
        module.set_zone_profile("zone_living", profile)
        test_time = datetime(2025, 1, 1, 19, 0, 0, tzinfo=timezone.utc)
        module.get_time_context("zone_living", at_time=test_time)
        assert module.is_evening("zone_living") is True
    
    def test_is_weekend(self):
        module = TimeOfDayModule()
        profile = TimeProfile("p1", "Test", "zone_living")
        module.set_zone_profile("zone_living", profile)
        test_time = datetime(2025, 1, 4, 12, 0, 0, tzinfo=timezone.utc)  # Saturday
        module.get_time_context("zone_living", at_time=test_time)
        assert module.is_weekend("zone_living") is True
    
    def test_is_holiday(self):
        module = TimeOfDayModule()
        module.add_holiday_date("2025-01-01")
        profile = TimeProfile("p1", "Test", "zone_living")
        module.set_zone_profile("zone_living", profile)
        test_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        module.get_time_context("zone_living", at_time=test_time)
        assert module.is_holiday("zone_living") is True
    
    def test_get_phase(self):
        module = TimeOfDayModule()
        profile = TimeProfile("p1", "Test", "zone_living")
        module.set_zone_profile("zone_living", profile)
        test_time = datetime(2025, 1, 1, 14, 0, 0, tzinfo=timezone.utc)
        module.get_time_context("zone_living", at_time=test_time)
        assert module.get_phase("zone_living") == TimeOfDayPhase.AFTERNOON
    
    def test_get_season(self):
        module = TimeOfDayModule()
        profile = TimeProfile("p1", "Test", "zone_living")
        module.set_zone_profile("zone_living", profile)
        test_time = datetime(2025, 7, 15, 12, 0, 0, tzinfo=timezone.utc)
        module.get_time_context("zone_living", at_time=test_time)
        assert module.get_season("zone_living") == Season.SUMMER
    
    def test_get_daylight_factor(self):
        module = TimeOfDayModule()
        profile = TimeProfile("p1", "Test", "zone_living")
        module.set_zone_profile("zone_living", profile)
        test_time = datetime(2025, 6, 15, 12, 0, 0, tzinfo=timezone.utc)
        module.get_time_context("zone_living", at_time=test_time)
        assert module.get_daylight_factor("zone_living") > 0
    
    def test_get_statistics(self):
        module = TimeOfDayModule()
        module.set_zone_profile("zone_1", TimeProfile("p1", "P1", "zone_1"))
        module.add_holiday_date("2025-01-01")
        stats = module.get_statistics()
        assert stats["total_zones"] == 1
        assert stats["total_holidays"] == 1
    
    def test_history_limited_to_1000(self):
        module = TimeOfDayModule()
        profile = TimeProfile("p1", "Test", "zone_living")
        module.set_zone_profile("zone_living", profile)
        for i in range(1500):
            test_time = datetime(2025, 1, 1, i % 24, 0, 0, tzinfo=timezone.utc)
            module.get_time_context("zone_living", at_time=test_time)
        assert len(module._time_history.get("zone_living", [])) == 1000
    
    def test_events_limited_to_100(self):
        module = TimeOfDayModule()
        profile = TimeProfile("p1", "Test", "zone_living")
        module.set_zone_profile("zone_living", profile)
        for i in range(150):
            test_time = datetime(2025, 1, 1, i % 24, 0, 0, tzinfo=timezone.utc)
            module.get_time_context("zone_living", at_time=test_time)
        assert len(module._time_events.get("zone_living", [])) <= 100
    
    def test_multiple_zones_independent(self):
        module = TimeOfDayModule()
        module.set_zone_profile("zone_1", TimeProfile("p1", "P1", "zone_1"))
        module.set_zone_profile("zone_2", TimeProfile("p2", "P2", "zone_2"))
        test_time_1 = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        module.get_time_context("zone_1", at_time=test_time_1)
        test_time_2 = datetime(2025, 1, 1, 22, 0, 0, tzinfo=timezone.utc)
        module.get_time_context("zone_2", at_time=test_time_2)
        assert module.get_phase("zone_1") == TimeOfDayPhase.MORNING
        assert module.get_phase("zone_2") == TimeOfDayPhase.EVENING
    
    def test_create_module_returns_instance(self):
        assert isinstance(create_time_of_day_module(), TimeOfDayModule)
    
    def test_daylight_factor_bounds(self):
        module = TimeOfDayModule()
        profile = TimeProfile("p1", "Test", "zone_living")
        for hour in range(24):
            test_time = datetime(2025, 6, 15, hour, 0, 0, tzinfo=timezone.utc)
            factor = module._calculate_daylight_factor(test_time, profile)
            assert 0.0 <= factor <= 1.0
    
    def test_sunset_factor_bounds(self):
        module = TimeOfDayModule()
        for phase in TimeOfDayPhase:
            factor = module._calculate_sunset_factor(None, phase)
            assert 0.0 <= factor <= 1.0
