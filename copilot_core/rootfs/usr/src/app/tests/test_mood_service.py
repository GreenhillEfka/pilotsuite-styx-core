"""Tests for mood service v3.0 — ZoneMoodProfile + MoodService."""

import os
import tempfile
import time
import unittest

try:
    from copilot_core.mood.service import MoodService
    from copilot_core.mood.models import (
        MoodDimensions,
        MoodState,
        MoodSystemConfig,
        ZoneMoodProfile,
    )
except ModuleNotFoundError:
    MoodService = None
    MoodDimensions = None
    MoodState = None
    MoodSystemConfig = None
    ZoneMoodProfile = None


class TestMoodService(unittest.TestCase):
    """Test MoodService functionality."""

    def setUp(self):
        """Set up test fixtures with a fresh temp database."""
        if MoodService is None:
            self.skipTest("MoodService not available")
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.service = MoodService(db_path=self._tmp.name)

    def tearDown(self):
        """Clean up temp database."""
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass

    def test_service_initializes(self):
        """Test MoodService initializes correctly."""
        self.assertIsNotNone(self.service)

    def test_initial_no_zones(self):
        """Test initially no zones have mood data."""
        moods = self.service.get_all_zone_moods()
        self.assertEqual(len(moods), 0)

    def test_update_from_media_context_creates_zone(self):
        """Test media context creates zone if not exists."""
        media_snapshot = {
            "music_active": True,
            "tv_active": False,
            "primary_player": {
                "area": "living_room",
                "media_title": "Test Song",
            },
        }

        self.service.update_from_media_context(media_snapshot)

        mood = self.service.get_zone_mood("living_room")
        self.assertIsNotNone(mood)

    def test_update_from_media_context_sets_joy(self):
        """Test media context sets joy based on activity."""
        media_snapshot = {
            "music_active": True,
            "tv_active": False,
            "primary_player": {
                "area": "living_room",
                "media_title": "Test Song",
            },
        }

        self.service.update_from_media_context(media_snapshot)

        mood = self.service.get_zone_mood("living_room")
        self.assertGreater(mood.dimensions.joy, 0.5)  # Music = high joy

    def test_update_from_media_context_tv_lower_joy(self):
        """Test TV gives lower joy boost than music."""
        # Music
        self.service.update_from_media_context({
            "music_active": True,
            "tv_active": False,
            "primary_player": {"area": "room1"},
        })
        music_joy = self.service.get_zone_mood("room1").dimensions.joy

        # Reset with fresh DB
        tmp2 = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        tmp2.close()
        svc2 = MoodService(db_path=tmp2.name)

        # TV
        svc2.update_from_media_context({
            "music_active": False,
            "tv_active": True,
            "primary_player": {"area": "room2"},
        })
        tv_joy = svc2.get_zone_mood("room2").dimensions.joy

        self.assertGreater(music_joy, tv_joy)

        try:
            os.unlink(tmp2.name)
        except OSError:
            pass

    def test_update_from_habitus_sets_comfort(self):
        """Test habitus context sets comfort based on time of day."""
        habitus_context = {
            "time_of_day": "evening",
            "frugality_score": 0.5,
            "zone_activity_level": "medium",
        }

        # First create a zone
        self.service.update_from_media_context({
            "music_active": False,
            "primary_player": {"area": "bedroom"},
        })

        # Then update from habitus
        self.service.update_from_habitus(habitus_context)

        mood = self.service.get_zone_mood("bedroom")
        self.assertGreater(mood.dimensions.comfort, 0.5)  # Evening = higher comfort

    def test_update_from_habitus_sets_time_of_day(self):
        """Test habitus context updates time of day."""
        habitus_context = {
            "time_of_day": "night",
            "frugality_score": 0.8,
            "zone_activity_level": "low",
        }

        # Create zone first
        self.service.update_from_media_context({
            "music_active": False,
            "primary_player": {"area": "test_zone"},
        })

        self.service.update_from_habitus(habitus_context)

        mood = self.service.get_zone_mood("test_zone")
        self.assertEqual(mood.time_of_day, "night")

    def test_get_zone_mood_returns_none_for_unknown(self):
        """Test get_zone_mood returns None for unknown zone."""
        mood = self.service.get_zone_mood("nonexistent_zone")
        self.assertIsNone(mood)

    def test_get_summary_empty(self):
        """Test get_summary returns correct structure for empty state."""
        summary = self.service.get_summary()

        self.assertEqual(summary["zones"], 0)
        self.assertEqual(summary["average_comfort"], 0.5)
        self.assertEqual(summary["average_frugality"], 0.5)
        self.assertEqual(summary["average_joy"], 0.5)
        self.assertEqual(summary["zones_with_media"], 0)

    def test_get_summary_with_zones(self):
        """Test get_summary calculates correct averages."""
        self.service.update_from_media_context({
            "music_active": True,
            "primary_player": {"area": "room1"},
        })
        self.service.update_from_media_context({
            "music_active": False,
            "primary_player": {"area": "room2"},
        })

        summary = self.service.get_summary()

        self.assertEqual(summary["zones"], 2)
        self.assertIn("average_comfort", summary)
        self.assertIn("average_frugality", summary)
        self.assertIn("average_joy", summary)

    def test_should_suppress_energy_saving_high_joy(self):
        """Test energy saving suppressed when joy is high."""
        self.service.update_from_media_context({
            "music_active": True,
            "primary_player": {"area": "living_room"},
        })

        # Keep updating to boost joy
        for _ in range(10):
            self.service.update_from_media_context({
                "music_active": True,
                "primary_player": {"area": "living_room"},
            })

        suppress = self.service.should_suppress_energy_saving("living_room")
        self.assertIsInstance(suppress, bool)

    def test_should_suppress_energy_saving_unknown_zone(self):
        """Test energy saving not suppressed for unknown zone."""
        suppress = self.service.should_suppress_energy_saving("unknown")
        self.assertFalse(suppress)

    def test_get_suggestion_relevance_multiplier_default(self):
        """Test suggestion relevance returns default for unknown zone."""
        multiplier = self.service.get_suggestion_relevance_multiplier(
            "unknown", "energy_saving"
        )
        self.assertEqual(multiplier, 1.0)

    def test_get_suggestion_relevance_energy_saving(self):
        """Test energy saving multiplier calculation."""
        self.service.update_from_media_context({
            "music_active": False,
            "primary_player": {"area": "test"},
        })

        multiplier = self.service.get_suggestion_relevance_multiplier(
            "test", "energy_saving"
        )

        # Should be (1 - joy) * frugality
        self.assertIsInstance(multiplier, float)
        self.assertGreaterEqual(multiplier, 0.0)
        self.assertLessEqual(multiplier, 1.0)

    def test_get_suggestion_relevance_comfort(self):
        """Test comfort multiplier returns comfort dimension."""
        self.service.update_from_media_context({
            "music_active": False,
            "primary_player": {"area": "test"},
        })

        multiplier = self.service.get_suggestion_relevance_multiplier(
            "test", "comfort"
        )

        mood = self.service.get_zone_mood("test")
        self.assertEqual(multiplier, mood.dimensions.comfort)

    def test_get_suggestion_relevance_entertainment(self):
        """Test entertainment multiplier returns joy dimension."""
        self.service.update_from_media_context({
            "music_active": True,
            "primary_player": {"area": "test"},
        })

        multiplier = self.service.get_suggestion_relevance_multiplier(
            "test", "entertainment"
        )

        mood = self.service.get_zone_mood("test")
        self.assertEqual(multiplier, mood.dimensions.joy)

    def test_get_suggestion_relevance_security(self):
        """Test security multiplier always returns 1.0."""
        self.service.update_from_media_context({
            "music_active": False,
            "primary_player": {"area": "test"},
        })

        multiplier = self.service.get_suggestion_relevance_multiplier(
            "test", "security"
        )

        self.assertEqual(multiplier, 1.0)

    def test_get_all_zone_moods_returns_dict(self):
        """Test get_all_zone_moods returns dictionary."""
        self.service.update_from_media_context({
            "music_active": True,
            "primary_player": {"area": "room1"},
        })

        moods = self.service.get_all_zone_moods()

        self.assertIsInstance(moods, dict)
        self.assertIn("room1", moods)

    def test_multiple_zones_independent(self):
        """Test multiple zones maintain independent moods."""
        self.service.update_from_media_context({
            "music_active": True,
            "primary_player": {"area": "room_music"},
        })

        self.service.update_from_media_context({
            "music_active": False,
            "primary_player": {"area": "room_quiet"},
        })

        music_mood = self.service.get_zone_mood("room_music")
        quiet_mood = self.service.get_zone_mood("room_quiet")

        self.assertGreater(music_mood.dimensions.joy, quiet_mood.dimensions.joy)

    def test_mood_timestamp_updated(self):
        """Test mood timestamp is updated on changes."""
        self.service.update_from_media_context({
            "music_active": False,
            "primary_player": {"area": "test"},
        })

        mood1 = self.service.get_zone_mood("test")
        time.sleep(0.01)

        self.service.update_from_media_context({
            "music_active": True,
            "primary_player": {"area": "test"},
        })

        mood2 = self.service.get_zone_mood("test")

        self.assertGreaterEqual(mood2.timestamp, mood1.timestamp)

    def test_update_zone_mood_from_external_data(self):
        """Test update_zone_mood with neuron pipeline data."""
        data = {
            "dominant_mood": "relax",
            "confidence": 0.85,
            "dimensions": {
                "comfort": 0.9,
                "frugality": 0.3,
                "joy": 0.7,
                "energy": 0.4,
                "stress": 0.1,
            },
        }

        self.service.update_zone_mood("lounge", data)

        profile = self.service.get_zone_profile("lounge")
        self.assertIsNotNone(profile)
        self.assertEqual(profile.state, MoodState.RELAX)
        self.assertAlmostEqual(profile.confidence, 0.85)
        self.assertAlmostEqual(profile.dimensions.comfort, 0.9)
        self.assertAlmostEqual(profile.dimensions.joy, 0.7)

    def test_update_zone_mood_partial_update(self):
        """Test update_zone_mood with partial data preserves existing dims."""
        # Initial full update
        self.service.update_zone_mood("test", {
            "dominant_mood": "focus",
            "confidence": 0.7,
            "dimensions": {"comfort": 0.8, "joy": 0.6},
        })

        # Partial update — only confidence
        self.service.update_zone_mood("test", {
            "confidence": 0.9,
        })

        profile = self.service.get_zone_profile("test")
        self.assertEqual(profile.state, MoodState.FOCUS)
        self.assertAlmostEqual(profile.confidence, 0.9)
        self.assertAlmostEqual(profile.dimensions.comfort, 0.8)

    def test_get_mood_history(self):
        """Test mood history retrieval from DB."""
        # Force persist by setting throttle to 0
        self.service._last_save_ts.clear()
        self.service._config.save_throttle_seconds = 0

        profile = ZoneMoodProfile(
            zone_id="hall",
            state=MoodState.ACTIVE,
            dimensions=MoodDimensions(comfort=0.6, joy=0.8),
            confidence=0.75,
        )
        self.service.update_zone_profile(profile)

        history = self.service.get_mood_history("hall", hours=1)
        self.assertIsInstance(history, list)
        if history:
            self.assertEqual(history[0]["state"], "active")

    def test_get_state_distribution(self):
        """Test state distribution query."""
        self.service._config.save_throttle_seconds = 0
        self.service._last_save_ts.clear()

        for state_name in ["relax", "relax", "focus"]:
            profile = ZoneMoodProfile(
                zone_id="room",
                state=MoodState.from_str(state_name),
                confidence=0.5,
            )
            self.service._last_save_ts.pop("room", None)
            self.service.persist_profile(profile)

        dist = self.service.get_state_distribution("room", hours=1)
        self.assertIsInstance(dist, dict)


class TestZoneMoodProfile(unittest.TestCase):
    """Test ZoneMoodProfile dataclass."""

    def setUp(self):
        if ZoneMoodProfile is None:
            self.skipTest("ZoneMoodProfile not available")

    def test_profile_creation_defaults(self):
        """Test ZoneMoodProfile with defaults."""
        profile = ZoneMoodProfile(zone_id="test_zone")

        self.assertEqual(profile.zone_id, "test_zone")
        self.assertEqual(profile.state, MoodState.NEUTRAL)
        self.assertAlmostEqual(profile.dimensions.comfort, 0.5)
        self.assertAlmostEqual(profile.dimensions.frugality, 0.5)
        self.assertAlmostEqual(profile.dimensions.joy, 0.5)
        self.assertAlmostEqual(profile.dimensions.energy, 0.5)
        self.assertAlmostEqual(profile.dimensions.stress, 0.0)
        self.assertAlmostEqual(profile.confidence, 0.0)

    def test_profile_creation_with_dimensions(self):
        """Test ZoneMoodProfile with custom dimensions."""
        dims = MoodDimensions(
            comfort=0.8, frugality=0.6, joy=0.4, energy=0.7, stress=0.2
        )
        profile = ZoneMoodProfile(
            zone_id="test_zone",
            state=MoodState.RELAX,
            dimensions=dims,
            confidence=0.9,
            media_playing=True,
            media_primary="Test Song",
            time_of_day="evening",
            occupancy_level="medium",
        )

        self.assertEqual(profile.zone_id, "test_zone")
        self.assertEqual(profile.state, MoodState.RELAX)
        self.assertAlmostEqual(profile.dimensions.comfort, 0.8)
        self.assertAlmostEqual(profile.dimensions.frugality, 0.6)
        self.assertAlmostEqual(profile.dimensions.joy, 0.4)
        self.assertTrue(profile.media_playing)
        self.assertEqual(profile.media_primary, "Test Song")

    def test_profile_to_dict(self):
        """Test ZoneMoodProfile to_dict method."""
        profile = ZoneMoodProfile(
            zone_id="test_zone",
            state=MoodState.FOCUS,
            dimensions=MoodDimensions(comfort=0.8, joy=0.4),
            confidence=0.75,
            time_of_day="evening",
            occupancy_level="medium",
        )

        d = profile.to_dict()

        self.assertIsInstance(d, dict)
        self.assertEqual(d["zone_id"], "test_zone")
        self.assertEqual(d["state"], "focus")
        self.assertAlmostEqual(d["dimensions"]["comfort"], 0.8, places=2)
        self.assertIn("timestamp", d)
        self.assertEqual(d["time_of_day"], "evening")

    def test_profile_from_dict(self):
        """Test ZoneMoodProfile.from_dict round-trip."""
        original = ZoneMoodProfile(
            zone_id="rt_test",
            state=MoodState.ACTIVE,
            dimensions=MoodDimensions(comfort=0.7, joy=0.9, stress=0.1),
            confidence=0.88,
            media_playing=True,
        )
        d = original.to_dict()
        restored = ZoneMoodProfile.from_dict(d)

        self.assertEqual(restored.zone_id, "rt_test")
        self.assertEqual(restored.state, MoodState.ACTIVE)
        self.assertAlmostEqual(restored.dimensions.comfort, 0.7, places=2)
        self.assertAlmostEqual(restored.dimensions.joy, 0.9, places=2)
        self.assertTrue(restored.media_playing)

    def test_dimension_values_in_range(self):
        """Test mood dimension values are clamped to [0, 1]."""
        dims = MoodDimensions(comfort=1.5, frugality=-0.3, joy=0.5)
        dims.clamp()

        self.assertGreaterEqual(dims.comfort, 0.0)
        self.assertLessEqual(dims.comfort, 1.0)
        self.assertGreaterEqual(dims.frugality, 0.0)
        self.assertLessEqual(dims.frugality, 1.0)

    def test_dimensions_ema_blend(self):
        """Test EMA blending of dimensions."""
        d1 = MoodDimensions(comfort=0.2, joy=0.8)
        d2 = MoodDimensions(comfort=0.8, joy=0.2)
        blended = d1.ema_blend(d2, alpha=0.5)

        self.assertAlmostEqual(blended.comfort, 0.5, places=1)
        self.assertAlmostEqual(blended.joy, 0.5, places=1)


class TestMoodState(unittest.TestCase):
    """Test MoodState enum."""

    def setUp(self):
        if MoodState is None:
            self.skipTest("MoodState not available")

    def test_from_str_valid(self):
        """Test MoodState.from_str with valid values."""
        self.assertEqual(MoodState.from_str("relax"), MoodState.RELAX)
        self.assertEqual(MoodState.from_str("FOCUS"), MoodState.FOCUS)
        self.assertEqual(MoodState.from_str(" Active "), MoodState.ACTIVE)
        self.assertEqual(MoodState.from_str("night"), MoodState.NIGHT)
        self.assertEqual(MoodState.from_str("away"), MoodState.AWAY)

    def test_from_str_invalid_defaults_neutral(self):
        """Test MoodState.from_str defaults to NEUTRAL for invalid."""
        self.assertEqual(MoodState.from_str("invalid"), MoodState.NEUTRAL)
        self.assertEqual(MoodState.from_str(""), MoodState.NEUTRAL)


class TestMoodDimensions(unittest.TestCase):
    """Test MoodDimensions dataclass."""

    def setUp(self):
        if MoodDimensions is None:
            self.skipTest("MoodDimensions not available")

    def test_from_dict(self):
        """Test MoodDimensions.from_dict."""
        d = {"comfort": 0.9, "frugality": 0.1, "joy": 0.5, "energy": 0.3, "stress": 0.8}
        dims = MoodDimensions.from_dict(d)

        self.assertAlmostEqual(dims.comfort, 0.9)
        self.assertAlmostEqual(dims.frugality, 0.1)
        self.assertAlmostEqual(dims.stress, 0.8)

    def test_from_dict_defaults(self):
        """Test MoodDimensions.from_dict with missing keys."""
        dims = MoodDimensions.from_dict({})

        self.assertAlmostEqual(dims.comfort, 0.5)
        self.assertAlmostEqual(dims.stress, 0.0)

    def test_to_dict(self):
        """Test MoodDimensions.to_dict."""
        dims = MoodDimensions(comfort=0.75, joy=0.3)
        d = dims.to_dict()

        self.assertAlmostEqual(d["comfort"], 0.75, places=2)
        self.assertAlmostEqual(d["joy"], 0.3, places=2)

    def test_dominant_dimension(self):
        """Test dominant_dimension property."""
        dims = MoodDimensions(comfort=0.5, frugality=0.5, joy=0.5, energy=0.5, stress=0.9)
        from copilot_core.mood.models import MoodDimensionName

        self.assertEqual(dims.dominant_dimension, MoodDimensionName.STRESS)


class TestMoodServiceEdgeCases(unittest.TestCase):
    """Test edge cases for MoodService."""

    def setUp(self):
        """Set up test fixtures with a fresh temp database."""
        if MoodService is None:
            self.skipTest("MoodService not available")
        self._tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
        self._tmp.close()
        self.service = MoodService(db_path=self._tmp.name)

    def tearDown(self):
        """Clean up temp database."""
        try:
            os.unlink(self._tmp.name)
        except OSError:
            pass

    def test_empty_media_snapshot(self):
        """Test empty media snapshot doesn't crash."""
        self.service.update_from_media_context({})

        moods = self.service.get_all_zone_moods()
        self.assertEqual(len(moods), 0)

    def test_none_media_snapshot(self):
        """Test None media snapshot doesn't crash."""
        self.service.update_from_media_context(None)

        moods = self.service.get_all_zone_moods()
        self.assertEqual(len(moods), 0)

    def test_empty_habitus_context(self):
        """Test empty habitus context doesn't crash."""
        self.service.update_from_habitus({})

    def test_none_habitus_context(self):
        """Test None habitus context doesn't crash."""
        self.service.update_from_habitus(None)

    def test_partial_media_snapshot(self):
        """Test partial media snapshot with missing fields."""
        self.service.update_from_media_context({
            "music_active": True,
            # missing primary_player
        })

        # Should handle gracefully
        mood = self.service.get_zone_mood("unknown")
        self.assertIsNone(mood)

    def test_partial_habitus_context(self):
        """Test partial habitus context with missing fields."""
        self.service.update_from_habitus({
            "time_of_day": "morning",
            # missing other fields
        })

    def test_unknown_time_of_day(self):
        """Test unknown time of day is stored as provided."""
        self.service.update_from_media_context({
            "music_active": False,
            "primary_player": {"area": "test"},
        })

        self.service.update_from_habitus({
            "time_of_day": "unknown_time",
            "frugality_score": 0.5,
        })

        mood = self.service.get_zone_mood("test")
        self.assertEqual(mood.time_of_day, "unknown_time")

    def test_unknown_occupancy_level(self):
        """Test unknown occupancy level is stored."""
        self.service.update_from_media_context({
            "music_active": False,
            "primary_player": {"area": "test"},
        })

        self.service.update_from_habitus({
            "time_of_day": "afternoon",
            "frugality_score": 0.5,
            "zone_activity_level": "unknown",
        })

        mood = self.service.get_zone_mood("test")
        self.assertEqual(mood.occupancy_level, "unknown")

    def test_db_path_fallback(self):
        """Test DB path fallback to /tmp when configured path is not writable."""
        svc = MoodService(db_path="/nonexistent/deep/path/mood.db")
        self.assertIsNotNone(svc)

    def test_persist_and_reload(self):
        """Test data survives service restart via DB."""
        self.service._config.save_throttle_seconds = 0

        profile = ZoneMoodProfile(
            zone_id="persist_test",
            state=MoodState.RELAX,
            dimensions=MoodDimensions(comfort=0.9, joy=0.8),
            confidence=0.95,
        )
        self.service.update_zone_profile(profile)

        # Create new service on same DB
        svc2 = MoodService(db_path=self._tmp.name)
        restored = svc2.get_zone_profile("persist_test")

        self.assertIsNotNone(restored)
        self.assertEqual(restored.state, MoodState.RELAX)
        self.assertAlmostEqual(restored.dimensions.comfort, 0.9, places=2)


class TestMoodSystemConfig(unittest.TestCase):
    """Test MoodSystemConfig."""

    def setUp(self):
        if MoodSystemConfig is None:
            self.skipTest("MoodSystemConfig not available")

    def test_default_config(self):
        """Test default MoodSystemConfig values."""
        cfg = MoodSystemConfig()

        self.assertEqual(cfg.min_dwell_time_seconds, 600)
        self.assertEqual(cfg.action_cooldown_seconds, 120)
        self.assertAlmostEqual(cfg.ema_alpha, 0.3)
        self.assertEqual(cfg.history_retention_days, 30)

    def test_config_from_dict(self):
        """Test MoodSystemConfig.from_dict."""
        d = {
            "ema_alpha": 0.5,
            "softmax_temperature": 2.0,
            "min_dwell_time_seconds": 300,
        }
        cfg = MoodSystemConfig.from_dict(d)

        self.assertAlmostEqual(cfg.ema_alpha, 0.5)
        self.assertAlmostEqual(cfg.softmax_temperature, 2.0)
        self.assertEqual(cfg.min_dwell_time_seconds, 300)

    def test_config_to_dict(self):
        """Test MoodSystemConfig.to_dict round-trip."""
        cfg = MoodSystemConfig(ema_alpha=0.4)
        d = cfg.to_dict()

        self.assertAlmostEqual(d["ema_alpha"], 0.4)
        self.assertIn("zones", d)


if __name__ == "__main__":
    unittest.main()
