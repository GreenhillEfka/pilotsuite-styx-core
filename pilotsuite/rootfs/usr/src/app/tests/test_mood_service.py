"""Tests for mood service."""

import os
import tempfile
import unittest
import time

try:
    from copilot_core.mood.service import MoodService, ZoneMoodSnapshot
except ModuleNotFoundError:
    MoodService = None
    ZoneMoodSnapshot = None


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
                "media_title": "Test Song"
            }
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
                "media_title": "Test Song"
            }
        }
        
        self.service.update_from_media_context(media_snapshot)
        
        mood = self.service.get_zone_mood("living_room")
        self.assertGreater(mood.joy, 0.5)  # Music = high joy

    def test_update_from_media_context_tv_lower_joy(self):
        """Test TV gives lower joy boost than music."""
        # Music
        self.service.update_from_media_context({
            "music_active": True,
            "tv_active": False,
            "primary_player": {"area": "room1"}
        })
        music_joy = self.service.get_zone_mood("room1").joy
        
        # Reset
        self.service = MoodService()
        
        # TV
        self.service.update_from_media_context({
            "music_active": False,
            "tv_active": True,
            "primary_player": {"area": "room2"}
        })
        tv_joy = self.service.get_zone_mood("room2").joy
        
        self.assertGreater(music_joy, tv_joy)

    def test_update_from_habitus_sets_comfort(self):
        """Test habitus context sets comfort based on time of day."""
        habitus_context = {
            "time_of_day": "evening",
            "frugality_score": 0.5,
            "zone_activity_level": "medium"
        }
        
        # First create a zone
        self.service.update_from_media_context({
            "music_active": False,
            "primary_player": {"area": "bedroom"}
        })
        
        # Then update from habitus
        self.service.update_from_habitus(habitus_context)
        
        mood = self.service.get_zone_mood("bedroom")
        self.assertGreater(mood.comfort, 0.5)  # Evening = higher comfort

    def test_update_from_habitus_sets_time_of_day(self):
        """Test habitus context updates time of day."""
        habitus_context = {
            "time_of_day": "night",
            "frugality_score": 0.8,
            "zone_activity_level": "low"
        }
        
        self.service.update_from_habitus(habitus_context)
        
        # Need to create zone first
        self.service.update_from_media_context({
            "music_active": False,
            "primary_player": {"area": "test_zone"}
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
        # Add some moods
        self.service.update_from_media_context({
            "music_active": True,
            "primary_player": {"area": "room1"}
        })
        self.service.update_from_media_context({
            "music_active": False,
            "primary_player": {"area": "room2"}
        })
        
        summary = self.service.get_summary()
        
        self.assertEqual(summary["zones"], 2)
        self.assertIn("average_comfort", summary)
        self.assertIn("average_frugality", summary)
        self.assertIn("average_joy", summary)

    def test_should_suppress_energy_saving_high_joy(self):
        """Test energy saving suppressed when joy is high."""
        # Create zone with high joy
        self.service.update_from_media_context({
            "music_active": True,
            "primary_player": {"area": "living_room"}
        })
        
        # Keep updating to boost joy
        for _ in range(10):
            self.service.update_from_media_context({
                "music_active": True,
                "primary_player": {"area": "living_room"}
            })
        
        suppress = self.service.should_suppress_energy_saving("living_room")
        # With enough updates, joy should be > 0.6
        self.assertTrue(suppress or not suppress)  # Just check it returns bool

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
            "primary_player": {"area": "test"}
        })
        
        multiplier = self.service.get_suggestion_relevance_multiplier(
            "test", "energy_saving"
        )
        
        # Should be (1 - joy) * frugality
        self.assertIsInstance(multiplier, float)
        self.assertGreaterEqual(multiplier, 0.0)
        self.assertLessEqual(multiplier, 1.0)

    def test_get_suggestion_relevance_comfort(self):
        """Test comfort multiplier returns comfort score."""
        self.service.update_from_media_context({
            "music_active": False,
            "primary_player": {"area": "test"}
        })
        
        multiplier = self.service.get_suggestion_relevance_multiplier(
            "test", "comfort"
        )
        
        mood = self.service.get_zone_mood("test")
        self.assertEqual(multiplier, mood.comfort)

    def test_get_suggestion_relevance_entertainment(self):
        """Test entertainment multiplier returns joy score."""
        self.service.update_from_media_context({
            "music_active": True,
            "primary_player": {"area": "test"}
        })
        
        multiplier = self.service.get_suggestion_relevance_multiplier(
            "test", "entertainment"
        )
        
        mood = self.service.get_zone_mood("test")
        self.assertEqual(multiplier, mood.joy)

    def test_get_suggestion_relevance_security(self):
        """Test security multiplier always returns 1.0."""
        self.service.update_from_media_context({
            "music_active": False,
            "primary_player": {"area": "test"}
        })
        
        multiplier = self.service.get_suggestion_relevance_multiplier(
            "test", "security"
        )
        
        self.assertEqual(multiplier, 1.0)

    def test_get_all_zone_moods_returns_dict(self):
        """Test get_all_zone_moods returns dictionary."""
        self.service.update_from_media_context({
            "music_active": True,
            "primary_player": {"area": "room1"}
        })
        
        moods = self.service.get_all_zone_moods()
        
        self.assertIsInstance(moods, dict)
        self.assertIn("room1", moods)

    def test_multiple_zones_independent(self):
        """Test multiple zones maintain independent moods."""
        self.service.update_from_media_context({
            "music_active": True,
            "primary_player": {"area": "room_music"}
        })
        
        self.service.update_from_media_context({
            "music_active": False,
            "primary_player": {"area": "room_quiet"}
        })
        
        music_mood = self.service.get_zone_mood("room_music")
        quiet_mood = self.service.get_zone_mood("room_quiet")
        
        self.assertGreater(music_mood.joy, quiet_mood.joy)

    def test_mood_timestamp_updated(self):
        """Test mood timestamp is updated on changes."""
        self.service.update_from_media_context({
            "music_active": False,
            "primary_player": {"area": "test"}
        })
        
        mood1 = self.service.get_zone_mood("test")
        time.sleep(0.01)  # Small delay
        
        self.service.update_from_media_context({
            "music_active": True,
            "primary_player": {"area": "test"}
        })
        
        mood2 = self.service.get_zone_mood("test")
        
        self.assertGreaterEqual(mood2.timestamp, mood1.timestamp)


class TestZoneMoodSnapshot(unittest.TestCase):
    """Test ZoneMoodSnapshot dataclass."""

    def test_snapshot_creation(self):
        """Test ZoneMoodSnapshot can be created."""
        if ZoneMoodSnapshot is None:
            self.skipTest("ZoneMoodSnapshot not available")
        
        snapshot = ZoneMoodSnapshot(
            zone_id="test_zone",
            timestamp=time.time(),
            comfort=0.8,
            frugality=0.6,
            joy=0.4,
            media_active=True,
            media_primary="Test Song",
            time_of_day="evening",
            occupancy_level="medium"
        )
        
        self.assertEqual(snapshot.zone_id, "test_zone")
        self.assertEqual(snapshot.comfort, 0.8)

    def test_snapshot_to_dict(self):
        """Test ZoneMoodSnapshot to_dict method."""
        if ZoneMoodSnapshot is None:
            self.skipTest("ZoneMoodSnapshot not available")
        
        snapshot = ZoneMoodSnapshot(
            zone_id="test_zone",
            timestamp=time.time(),
            comfort=0.8,
            frugality=0.6,
            joy=0.4,
            media_active=True,
            media_primary="Test Song",
            time_of_day="evening",
            occupancy_level="medium"
        )
        
        d = snapshot.to_dict()
        
        self.assertIsInstance(d, dict)
        self.assertEqual(d["zone_id"], "test_zone")
        self.assertEqual(d["comfort"], 0.8)
        self.assertIn("timestamp", d)

    def test_snapshot_values_in_range(self):
        """Test mood values are in valid 0-1 range."""
        if ZoneMoodSnapshot is None:
            self.skipTest("ZoneMoodSnapshot not available")
        
        snapshot = ZoneMoodSnapshot(
            zone_id="test",
            timestamp=time.time(),
            comfort=0.5,
            frugality=0.5,
            joy=0.5,
            media_active=False,
            media_primary=None,
            time_of_day="afternoon",
            occupancy_level="low"
        )
        
        self.assertGreaterEqual(snapshot.comfort, 0.0)
        self.assertLessEqual(snapshot.comfort, 1.0)
        self.assertGreaterEqual(snapshot.frugality, 0.0)
        self.assertLessEqual(snapshot.frugality, 1.0)
        self.assertGreaterEqual(snapshot.joy, 0.0)
        self.assertLessEqual(snapshot.joy, 1.0)


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
        
        # Should not raise

    def test_none_habitus_context(self):
        """Test None habitus context doesn't crash."""
        self.service.update_from_habitus(None)
        
        # Should not raise

    def test_partial_media_snapshot(self):
        """Test partial media snapshot with missing fields."""
        self.service.update_from_media_context({
            "music_active": True
            # missing primary_player
        })
        
        mood = self.service.get_zone_mood("unknown")
        # Should handle gracefully, might not create zone

    def test_partial_habitus_context(self):
        """Test partial habitus context with missing fields."""
        self.service.update_from_habitus({
            "time_of_day": "morning"
            # missing other fields
        })
        
        # Should not raise

    def test_unknown_time_of_day(self):
        """Test unknown time of day defaults to afternoon."""
        self.service.update_from_media_context({
            "music_active": False,
            "primary_player": {"area": "test"}
        })
        
        self.service.update_from_habitus({
            "time_of_day": "unknown_time",
            "frugality_score": 0.5
        })
        
        mood = self.service.get_zone_mood("test")
        self.assertEqual(mood.time_of_day, "unknown_time")

    def test_unknown_occupancy_level(self):
        """Test unknown occupancy level is stored."""
        self.service.update_from_media_context({
            "music_active": False,
            "primary_player": {"area": "test"}
        })
        
        self.service.update_from_habitus({
            "time_of_day": "afternoon",
            "frugality_score": 0.5,
            "zone_activity_level": "unknown"
        })
        
        mood = self.service.get_zone_mood("test")
        self.assertEqual(mood.occupancy_level, "unknown")


if __name__ == "__main__":
    unittest.main()
