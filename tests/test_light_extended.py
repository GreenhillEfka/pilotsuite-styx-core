"""Tests for Light Module Extensions — Slice 76."""
import pytest
from copilot_core.light.light_extended import (
    LightModuleExtended,
    LightSchedule,
    CircadianConfig,
    AdvancedScene,
    BulbStats,
    LightGroup,
    ColorMode,
    LightEffect,
    create_light_module_extended,
    create_reading_scene,
    create_relaxing_scene,
    create_movie_scene,
    create_sunrise_scene,
)
from datetime import datetime, timezone, timedelta


class TestColorMode:
    def test_color_mode_enum_values(self):
        assert ColorMode.WHITE.value == "white"
        assert ColorMode.COLOR_TEMP.value == "color_temp"
        assert ColorMode.RGB.value == "rgb"


class TestLightEffect:
    def test_effect_enum_values(self):
        assert LightEffect.NONE.value == "none"
        assert LightEffect.FADE_IN.value == "fade_in"
        assert LightEffect.SUNRISE.value == "sunrise"


class TestLightSchedule:
    def test_create_schedule(self):
        schedule = LightSchedule(
            schedule_id="sched_1",
            zone_id="zone_living",
            name="Morning On",
            start_time="07:00",
            action="turn_on",
        )
        assert schedule.enabled is True
        assert len(schedule.days_of_week) == 7
    
    def test_schedule_to_dict(self):
        schedule = LightSchedule(
            schedule_id="sched_1",
            zone_id="zone_living",
            name="Test",
            brightness=0.8,
            transition_seconds=5,
        )
        d = schedule.to_dict()
        assert d["brightness"] == 0.8
        assert d["transition_seconds"] == 5


class TestCircadianConfig:
    def test_create_circadian_config(self):
        config = CircadianConfig()
        assert config.enabled is True
        assert config.min_color_temp == 2700
        assert config.max_color_temp == 6500
    
    def test_circadian_custom_values(self):
        config = CircadianConfig(
            min_color_temp=3000,
            max_color_temp=6000,
            min_brightness=0.2,
            max_brightness=0.9,
        )
        assert config.min_color_temp == 3000
        assert config.max_brightness == 0.9
    
    def test_circadian_to_dict(self):
        config = CircadianConfig(
            enabled=True,
            sleep_mode_brightness=0.05,
            transition_speed_minutes=45,
        )
        d = config.to_dict()
        assert d["sleep_mode_brightness"] == 0.05


class TestAdvancedScene:
    def test_create_scene(self):
        scene = AdvancedScene(
            scene_id="scene_1",
            zone_id="zone_living",
            name="Reading",
            brightness=0.9,
        )
        assert scene.color_mode == ColorMode.COLOR_TEMP
        assert scene.effect == LightEffect.NONE
    
    def test_scene_with_effect(self):
        scene = AdvancedScene(
            scene_id="scene_1",
            zone_id="zone_living",
            name="Sunrise",
            brightness=0.8,
            effect=LightEffect.SUNRISE,
            transition_seconds=900,
        )
        assert scene.effect == LightEffect.SUNRISE
        assert scene.transition_seconds == 900
    
    def test_scene_to_dict(self):
        scene = AdvancedScene(
            scene_id="scene_1",
            zone_id="zone_living",
            name="Test",
            brightness=0.7,
            color_temp=4000,
            tags=["evening", "relaxing"],
        )
        d = scene.to_dict()
        assert d["tags"] == ["evening", "relaxing"]


class TestBulbStats:
    def test_create_stats(self):
        stats = BulbStats(
            entity_id="light.living",
            zone_id="zone_living",
        )
        assert stats.total_on_hours == 0.0
        assert stats.rated_lifetime_hours == 25000.0
    
    def test_lifetime_remaining_percent(self):
        stats = BulbStats(
            entity_id="light.living",
            zone_id="zone_living",
            total_on_hours=12500.0,
            rated_lifetime_hours=25000.0,
        )
        assert stats.lifetime_remaining_percent == 50.0
    
    def test_lifetime_remaining_zero(self):
        stats = BulbStats(
            entity_id="light.living",
            zone_id="zone_living",
            total_on_hours=30000.0,
            rated_lifetime_hours=25000.0,
        )
        assert stats.lifetime_remaining_percent == 0.0
    
    def test_stats_to_dict(self):
        stats = BulbStats(
            entity_id="light.living",
            zone_id="zone_living",
            total_on_hours=100.0,
            total_energy_wh=1000.0,
            on_off_cycles=50,
        )
        d = stats.to_dict()
        assert d["total_on_hours"] == 100.0
        assert d["on_off_cycles"] == 50


class TestLightGroup:
    def test_create_group(self):
        group = LightGroup(
            group_id="group_1",
            name="Downstairs",
            zone_ids=["zone_living", "zone_kitchen"],
            entity_ids=["light.living", "light.kitchen"],
        )
        assert group.sync_brightness is True
        assert group.sync_color is True
    
    def test_group_no_sync_effects(self):
        group = LightGroup(
            group_id="group_1",
            name="Test",
            zone_ids=["zone_1"],
            entity_ids=["light.test"],
            sync_effects=False,
        )
        assert group.sync_effects is False
    
    def test_group_to_dict(self):
        group = LightGroup(
            group_id="group_1",
            name="Test Group",
            zone_ids=["zone_1", "zone_2"],
            entity_ids=["light.l1", "light.l2"],
            master_zone="zone_1",
        )
        d = group.to_dict()
        assert d["master_zone"] == "zone_1"


class TestLightModuleExtended:
    def test_create_module(self):
        module = create_light_module_extended()
        assert module is not None
    
    def test_add_schedule(self):
        module = LightModuleExtended()
        
        schedule = LightSchedule(
            schedule_id="sched_1",
            zone_id="zone_living",
            name="Morning On",
            start_time="07:00",
            action="turn_on",
        )
        
        schedule_id = module.add_schedule(schedule)
        
        assert schedule_id == "sched_1"
    
    def test_remove_schedule(self):
        module = LightModuleExtended()
        
        schedule = LightSchedule("sched_1", "zone_living", "Test", start_time="07:00", action="turn_on")
        module.add_schedule(schedule)
        
        result = module.remove_schedule("sched_1")
        
        assert result is True
    
    def test_remove_nonexistent_schedule(self):
        module = LightModuleExtended()
        
        result = module.remove_schedule("nonexistent")
        
        assert result is False
    
    def test_add_scene(self):
        module = LightModuleExtended()
        
        scene = AdvancedScene(
            scene_id="scene_1",
            zone_id="zone_living",
            name="Reading",
            brightness=0.9,
        )
        
        scene_id = module.add_scene(scene)
        
        assert scene_id == "scene_1"
        assert module.get_scene("scene_1") is not None
    
    def test_remove_scene(self):
        module = LightModuleExtended()
        
        scene = AdvancedScene("scene_1", "zone_living", "Test", brightness=0.8)
        module.add_scene(scene)
        
        result = module.remove_scene("scene_1")
        
        assert result is True
    
    def test_set_circadian_config(self):
        module = LightModuleExtended()
        
        config = CircadianConfig(
            min_color_temp=3000,
            max_color_temp=5000,
        )
        
        result = module.set_circadian_config("zone_living", config)
        
        assert result is True
        assert module.get_circadian_config("zone_living") is not None
    
    def test_calculate_circadian_state_day(self):
        module = LightModuleExtended()
        
        config = CircadianConfig(
            min_color_temp=2700,
            max_color_temp=6500,
            min_brightness=0.2,
            max_brightness=1.0,
        )
        module.set_circadian_config("zone_living", config)
        
        # Mid-day
        test_time = datetime(2025, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
        state = module.calculate_circadian_state("zone_living", at_time=test_time)
        
        assert state["brightness"] == 1.0
        assert state["color_temp"] == 6500
    
    def test_calculate_circadian_state_night(self):
        module = LightModuleExtended()
        
        config = CircadianConfig(
            min_color_temp=2700,
            max_color_temp=6500,
            min_brightness=0.2,
            max_brightness=1.0,
            sleep_mode_brightness=0.05,
        )
        module.set_circadian_config("zone_living", config)
        
        # Night
        test_time = datetime(2025, 1, 1, 2, 0, 0, tzinfo=timezone.utc)
        state = module.calculate_circadian_state("zone_living", at_time=test_time)
        
        assert state["brightness"] == 0.05
        assert state["color_temp"] == 2700
    
    def test_calculate_circadian_disabled(self):
        module = LightModuleExtended()
        
        config = CircadianConfig(enabled=False)
        module.set_circadian_config("zone_living", config)
        
        state = module.calculate_circadian_state("zone_living")
        
        assert state["brightness"] is None
        assert state["color_temp"] is None
    
    def test_apply_scene_with_transition(self):
        module = LightModuleExtended()
        
        scene = AdvancedScene(
            scene_id="scene_1",
            zone_id="zone_living",
            name="Test",
            brightness=0.7,
            transition_seconds=5,
        )
        module.add_scene(scene)
        
        result = module.apply_scene_with_transition("zone_living", "scene_1")
        
        assert result["success"] is True
        assert result["target_brightness"] == 0.7
    
    def test_apply_nonexistent_scene(self):
        module = LightModuleExtended()
        
        result = module.apply_scene_with_transition("zone_living", "nonexistent")
        
        assert result["success"] is False
    
    def test_update_brightness_smooth(self):
        module = LightModuleExtended()
        
        result = module.update_brightness_smooth("zone_living", 0.8, transition_seconds=10)
        
        assert result["success"] is True
        assert result["to_brightness"] == 0.8
    
    def test_get_brightness(self):
        module = LightModuleExtended()
        
        module.update_brightness_smooth("zone_living", 0.6)
        
        brightness = module.get_brightness("zone_living")
        
        assert brightness == 0.6
    
    def test_add_bulb_stats(self):
        module = LightModuleExtended()
        
        stats = BulbStats(
            entity_id="light.living",
            zone_id="zone_living",
            power_rating_watts=10.0,
        )
        
        result = module.add_bulb_stats(stats)
        
        assert result is True
    
    def test_add_duplicate_bulb_stats(self):
        module = LightModuleExtended()
        
        stats = BulbStats(entity_id="light.living", zone_id="zone_living")
        module.add_bulb_stats(stats)
        
        result = module.add_bulb_stats(stats)
        
        assert result is False
    
    def test_update_bulb_usage(self):
        module = LightModuleExtended()
        
        stats = BulbStats(entity_id="light.living", zone_id="zone_living", power_rating_watts=10.0)
        module.add_bulb_stats(stats)
        
        module.update_bulb_usage("light.living", is_on=True, brightness=0.8, duration_minutes=60.0)
        
        updated = module.get_bulb_stats("light.living")
        
        assert updated.total_on_hours == 1.0
        assert updated.total_energy_wh == 8.0  # 10W * 0.8 * 1h
    
    def test_record_on_off_cycle(self):
        module = LightModuleExtended()
        
        stats = BulbStats(entity_id="light.living", zone_id="zone_living")
        module.add_bulb_stats(stats)
        
        module.record_on_off_cycle("light.living")
        module.record_on_off_cycle("light.living")
        
        updated = module.get_bulb_stats("light.living")
        
        assert updated.on_off_cycles == 2
    
    def test_create_light_group(self):
        module = LightModuleExtended()
        
        group = LightGroup(
            group_id="group_1",
            name="Downstairs",
            zone_ids=["zone_living", "zone_kitchen"],
            entity_ids=["light.living", "light.kitchen"],
        )
        
        group_id = module.create_light_group(group)
        
        assert group_id == "group_1"
        assert module.get_light_group("group_1") is not None
    
    def test_sync_group_brightness(self):
        module = LightModuleExtended()
        
        group = LightGroup(
            group_id="group_1",
            name="Test",
            zone_ids=["zone_1", "zone_2"],
            entity_ids=["light.l1", "light.l2"],
        )
        module.create_light_group(group)
        
        synced = module.sync_group_brightness("group_1", 0.7)
        
        assert len(synced) == 2
        assert module.get_brightness("zone_1") == 0.7
        assert module.get_brightness("zone_2") == 0.7
    
    def test_get_schedule_for_time(self):
        module = LightModuleExtended()
        
        schedule = LightSchedule(
            schedule_id="sched_1",
            zone_id="zone_living",
            name="Morning",
            start_time="07:00",
            end_time="09:00",
            action="turn_on",
            days_of_week=[0, 1, 2, 3, 4],  # Weekdays
        )
        module.add_schedule(schedule)
        
        # Monday 08:00
        test_time = datetime(2025, 1, 6, 8, 0, 0, tzinfo=timezone.utc)
        active = module.get_schedule_for_time("zone_living", at_time=test_time)
        
        assert len(active) == 1
    
    def test_get_schedule_outside_time(self):
        module = LightModuleExtended()
        
        schedule = LightSchedule(
            schedule_id="sched_1",
            zone_id="zone_living",
            name="Morning",
            start_time="07:00",
            end_time="09:00",
            action="turn_on",
        )
        module.add_schedule(schedule)
        
        # 10:00 - after end time
        test_time = datetime(2025, 1, 1, 10, 0, 0, tzinfo=timezone.utc)
        active = module.get_schedule_for_time("zone_living", at_time=test_time)
        
        assert len(active) == 0
    
    def test_get_zone_scenes(self):
        module = LightModuleExtended()
        
        module.add_scene(AdvancedScene("s1", "zone_1", "S1", brightness=0.8))
        module.add_scene(AdvancedScene("s2", "zone_1", "S2", brightness=0.6))
        module.add_scene(AdvancedScene("s3", "zone_2", "S3", brightness=0.7))
        
        scenes = module.get_zone_scenes("zone_1")
        
        assert len(scenes) == 2
    
    def test_get_active_effect(self):
        module = LightModuleExtended()
        
        module.update_brightness_smooth("zone_living", 0.8, transition_seconds=5)
        
        effect = module.get_active_effect("zone_living")
        
        assert effect is not None
        assert effect["type"] == "brightness_fade"
    
    def test_clear_effect(self):
        module = LightModuleExtended()
        
        module.update_brightness_smooth("zone_living", 0.8)
        
        result = module.clear_effect("zone_living")
        
        assert result is True
        assert module.get_active_effect("zone_living") is None
    
    def test_get_bulbs_needing_replacement(self):
        module = LightModuleExtended()
        
        # Low lifetime bulb
        stats1 = BulbStats(
            entity_id="light.old",
            zone_id="zone_living",
            total_on_hours=24000.0,
            rated_lifetime_hours=25000.0,
        )
        
        # Good bulb
        stats2 = BulbStats(
            entity_id="light.new",
            zone_id="zone_kitchen",
            total_on_hours=100.0,
            rated_lifetime_hours=25000.0,
        )
        
        module.add_bulb_stats(stats1)
        module.add_bulb_stats(stats2)
        
        replacements = module.get_bulbs_needing_replacement(threshold_percent=20.0)
        
        assert len(replacements) == 1
        assert replacements[0].entity_id == "light.old"
    
    def test_get_statistics(self):
        module = LightModuleExtended()
        
        module.add_schedule(LightSchedule("s1", "zone_1", "S1", start_time="07:00", action="turn_on"))
        module.add_scene(AdvancedScene("sc1", "zone_1", "SC1", brightness=0.8))
        
        stats = module.get_statistics()
        
        assert stats["total_schedules"] == 1
        assert stats["total_scenes"] == 1
    
    def test_create_module_returns_instance(self):
        assert isinstance(create_light_module_extended(), LightModuleExtended)
    
    def test_scene_with_rgb_color(self):
        scene = AdvancedScene(
            scene_id="scene_rgb",
            zone_id="zone_1",
            name="RGB Scene",
            brightness=0.8,
            color_rgb=(255, 100, 50),
            color_mode=ColorMode.RGB,
        )
        d = scene.to_dict()
        assert d["color_rgb"] == [255, 100, 50]
    
    def test_scene_with_tags(self):
        scene = AdvancedScene(
            scene_id="scene_tagged",
            zone_id="zone_1",
            name="Tagged",
            brightness=0.7,
            tags=["relaxing", "evening", "warm"],
        )
        d = scene.to_dict()
        assert len(d["tags"]) == 3
    
    def test_schedule_weekend_only(self):
        schedule = LightSchedule(
            schedule_id="sched_weekend",
            zone_id="zone_1",
            name="Weekend",
            start_time="09:00",
            action="turn_on",
            days_of_week=[5, 6],  # Saturday, Sunday
        )
        d = schedule.to_dict()
        assert d["days_of_week"] == [5, 6]
    
    def test_circadian_sunrise_offset(self):
        config = CircadianConfig(
            sunrise_offset_minutes=-30,  # 30 min before sunrise
            sunset_offset_minutes=30,  # 30 min after sunset
        )
        d = config.to_dict()
        assert d["sunrise_offset_minutes"] == -30
    
    def test_brightness_cache_persists(self):
        module = LightModuleExtended()
        
        module.update_brightness_smooth("zone_1", 0.5)
        module.update_brightness_smooth("zone_1", 0.7)
        
        assert module.get_brightness("zone_1") == 0.7
    
    def test_get_nonexistent_scene(self):
        module = LightModuleExtended()
        
        scene = module.get_scene("nonexistent")
        
        assert scene is None
    
    def test_get_nonexistent_light_group(self):
        module = LightModuleExtended()
        
        group = module.get_light_group("nonexistent")
        
        assert group is None
    
    def test_get_nonexistent_bulb_stats(self):
        module = LightModuleExtended()
        
        stats = module.get_bulb_stats("nonexistent")
        
        assert stats is None
    
    def test_clear_nonexistent_effect(self):
        module = LightModuleExtended()
        
        result = module.clear_effect("nonexistent")
        
        assert result is False
    
    def test_statistics_bulbs_tracked(self):
        module = LightModuleExtended()
        
        module.add_bulb_stats(BulbStats("light.l1", "zone_1"))
        module.add_bulb_stats(BulbStats("light.l2", "zone_2"))
        
        stats = module.get_statistics()
        
        assert stats["bulbs_tracked"] == 2
    
    def test_statistics_circadian_zones(self):
        module = LightModuleExtended()
        
        module.set_circadian_config("zone_1", CircadianConfig())
        module.set_circadian_config("zone_2", CircadianConfig())
        
        stats = module.get_statistics()
        
        assert stats["circadian_zones"] == 2
    
    def test_prebuilt_reading_scene(self):
        scene = create_reading_scene("zone_living")
        
        assert scene.brightness == 0.9
        assert scene.color_temp == 5000
        assert "focused" in scene.tags
    
    def test_prebuilt_relaxing_scene(self):
        scene = create_relaxing_scene("zone_living")
        
        assert scene.brightness == 0.4
        assert scene.color_temp == 3000
        assert "evening" in scene.tags
    
    def test_prebuilt_movie_scene(self):
        scene = create_movie_scene("zone_living")
        
        assert scene.brightness == 0.2
        assert "dim" in scene.tags
    
    def test_prebuilt_sunrise_scene(self):
        scene = create_sunrise_scene("zone_living")
        
        assert scene.effect == LightEffect.SUNRISE
        assert scene.transition_seconds == 900
        assert "wake-up" in scene.tags
    
    def test_apply_scene_wrong_zone(self):
        module = LightModuleExtended()
        
        scene = AdvancedScene("scene_1", "zone_living", "Test", brightness=0.8)
        module.add_scene(scene)
        
        result = module.apply_scene_with_transition("zone_kitchen", "scene_1")
        
        assert result["success"] is False
        assert result["error"] == "Scene not for this zone"
    
    def test_update_bulb_usage_nonexistent(self):
        module = LightModuleExtended()
        
        # Should not crash
        module.update_bulb_usage("nonexistent", is_on=True)
    
    def test_record_cycle_nonexistent(self):
        module = LightModuleExtended()
        
        # Should not crash
        module.record_on_off_cycle("nonexistent")
    
    def test_sync_group_no_sync_brightness(self):
        module = LightModuleExtended()
        
        group = LightGroup(
            group_id="group_1",
            name="Test",
            zone_ids=["zone_1"],
            entity_ids=["light.l1"],
            sync_brightness=False,
        )
        module.create_light_group(group)
        
        synced = module.sync_group_brightness("group_1", 0.8)
        
        assert len(synced) == 0
    
    def test_lifetime_remaining_edge_cases(self):
        stats = BulbStats(
            entity_id="light.test",
            zone_id="zone_1",
            total_on_hours=0.0,
            rated_lifetime_hours=0.0,  # Edge case
        )
        
        assert stats.lifetime_remaining_percent == 100.0
    
    def test_schedule_with_end_time_none(self):
        schedule = LightSchedule(
            schedule_id="sched_instant",
            zone_id="zone_1",
            name="Instant",
            start_time="08:00",
            end_time=None,
            action="turn_on",
        )
        d = schedule.to_dict()
        assert d["end_time"] is None
    
    def test_scene_duration_seconds(self):
        scene = AdvancedScene(
            scene_id="scene_timed",
            zone_id="zone_1",
            name="Timed",
            brightness=0.8,
            duration_seconds=1800,  # 30 minutes
        )
        d = scene.to_dict()
        assert d["duration_seconds"] == 1800
    
    def test_scene_priority(self):
        scene = AdvancedScene(
            scene_id="scene_high",
            zone_id="zone_1",
            name="High Priority",
            brightness=0.9,
            priority=90,
        )
        d = scene.to_dict()
        assert d["priority"] == 90
    
    def test_get_schedule_disabled(self):
        module = LightModuleExtended()
        
        schedule = LightSchedule(
            schedule_id="sched_disabled",
            zone_id="zone_1",
            name="Disabled",
            start_time="08:00",
            action="turn_on",
            enabled=False,
        )
        module.add_schedule(schedule)
        
        test_time = datetime(2025, 1, 1, 8, 30, 0, tzinfo=timezone.utc)
        active = module.get_schedule_for_time("zone_1", at_time=test_time)
        
        # Disabled schedules should not be returned
        assert len(active) == 0
    
    def test_get_schedule_wrong_day(self):
        module = LightModuleExtended()
        
        schedule = LightSchedule(
            schedule_id="sched_weekday",
            zone_id="zone_1",
            name="Weekday",
            start_time="08:00",
            action="turn_on",
            days_of_week=[0, 1, 2, 3, 4],  # Mon-Fri
        )
        module.add_schedule(schedule)
        
        # Saturday
        test_time = datetime(2025, 1, 4, 8, 30, 0, tzinfo=timezone.utc)
        active = module.get_schedule_for_time("zone_1", at_time=test_time)
        
        assert len(active) == 0
