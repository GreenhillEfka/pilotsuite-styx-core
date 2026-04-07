"""Tests for Multi-User Preference Learning (P1-003).

Tests user profiles, preference learning, and API endpoints.
"""
import json
import os
import tempfile
import time
import unittest
from pathlib import Path

from copilot_core.user_profiles import UserProfiles, get_user_profiles
from copilot_core.preference_learning import PreferenceLearner, get_preference_learner


class TestUserProfiles(unittest.TestCase):
    """Test user profile management."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_user_profiles.db")
        self.profiles = UserProfiles(db_path=self.db_path)
    
    def tearDown(self):
        # Cleanup
        try:
            os.remove(self.db_path)
            os.rmdir(self.temp_dir)
        except:
            pass
    
    def test_create_user(self):
        """Test creating a new user."""
        user = self.profiles.create_user(name="Alice")
        
        self.assertIsNotNone(user.user_id)
        self.assertEqual(user.name, "Alice")
        self.assertIsNone(user.voice_id)
        self.assertTrue(user.is_active)
    
    def test_create_user_with_voice(self):
        """Test creating user with voice ID."""
        user = self.profiles.create_user(name="Bob", voice_id="voice_abc123")
        
        self.assertEqual(user.voice_id, "voice_abc123")
        
        # Verify lookup by voice
        found = self.profiles.get_user_by_voice("voice_abc123")
        self.assertIsNotNone(found)
        self.assertEqual(found.name, "Bob")
    
    def test_identify_user_by_voice(self):
        """Test user identification by voice."""
        self.profiles.create_user(name="Charlie", voice_id="voice_charlie")
        
        # Identify existing user by voice
        user = self.profiles.identify_user(voice_id="voice_charlie")
        self.assertEqual(user.name, "Charlie")
    
    def test_identify_user_by_name(self):
        """Test user identification by name."""
        self.profiles.create_user(name="Diana")
        
        # Identify by name (case-insensitive)
        user = self.profiles.identify_user(name="diana")
        self.assertEqual(user.name, "Diana")
    
    def test_identify_creates_new_user(self):
        """Test that identify creates new user if not found."""
        user = self.profiles.identify_user(name="NewUser")
        
        self.assertIsNotNone(user.user_id)
        self.assertEqual(user.name, "NewUser")
    
    def test_update_user(self):
        """Test updating user profile."""
        user = self.profiles.create_user(name="Eve")
        
        updated = self.profiles.update_user(user.user_id, voice_id="voice_eve")
        
        self.assertEqual(updated.voice_id, "voice_eve")
    
    def test_record_interaction(self):
        """Test recording user interactions."""
        user = self.profiles.create_user(name="Frank")
        
        initial_count = user.interaction_count
        
        self.profiles.record_interaction(user.user_id)
        
        updated = self.profiles.get_user(user.user_id)
        self.assertEqual(updated.interaction_count, initial_count + 1)
    
    def test_get_all_users(self):
        """Test getting all users."""
        self.profiles.create_user(name="User1")
        self.profiles.create_user(name="User2")
        
        users = self.profiles.get_all_users()
        self.assertGreaterEqual(len(users), 2)
    
    def test_delete_user(self):
        """Test deleting a user."""
        user = self.profiles.create_user(name="ToDelete")
        
        result = self.profiles.delete_user(user.user_id)
        
        self.assertTrue(result)
        self.assertIsNone(self.profiles.get_user(user.user_id))
    
    def test_deactivate_user(self):
        """Test deactivating a user."""
        user = self.profiles.create_user(name="Inactive")
        
        result = self.profiles.deactivate_user(user.user_id)
        
        self.assertTrue(result)
        
        updated = self.profiles.get_user(user.user_id)
        self.assertFalse(updated.is_active)
        
        # Should not appear in active list
        active = self.profiles.get_active_users()
        self.assertNotIn(user.user_id, [u.user_id for u in active])
    
    def test_export_user_data(self):
        """Test GDPR data export."""
        user = self.profiles.create_user(name="ExportMe")
        
        export = self.profiles.export_user_data(user.user_id)
        
        self.assertIsNotNone(export)
        self.assertIn("user_profile", export)
        self.assertEqual(export["user_profile"]["name"], "ExportMe")


class TestPreferenceLearner(unittest.TestCase):
    """Test preference learning from conversations."""
    
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = os.path.join(self.temp_dir, "test_prefs.db")
        self.learner = PreferenceLearner(db_path=self.db_path)
    
    def tearDown(self):
        try:
            os.remove(self.db_path)
            os.rmdir(self.temp_dir)
        except:
            pass
    
    def test_extract_temperature_preference(self):
        """Test extracting temperature preference."""
        user_id = "test_user"
        text = "Ich mag es bei 22 Grad warm"
        
        prefs = self.learner.extract_preferences(user_id, text)
        
        self.assertEqual(len(prefs), 1)
        self.assertEqual(prefs[0].key, "preferred_temperature")
        self.assertEqual(prefs[0].value, "22")
        self.assertEqual(prefs[0].source, "explicit")
    
    def test_extract_wake_time(self):
        """Test extracting wake time preference."""
        user_id = "test_user"
        text = "Ich stehe um 6:30 auf"
        
        prefs = self.learner.extract_preferences(user_id, text)
        
        self.assertEqual(len(prefs), 1)
        self.assertEqual(prefs[0].key, "wake_time")
        self.assertEqual(prefs[0].value, "06:30")
    
    def test_extract_light_preference(self):
        """Test extracting light preference."""
        user_id = "test_user"
        text = "Abends mag ich das Licht gerne dunkel"
        
        prefs = self.learner.extract_preferences(user_id, text)
        
        self.assertEqual(len(prefs), 1)
        self.assertEqual(prefs[0].key, "light_preference")
        self.assertEqual(prefs[0].value, "dim")
    
    def test_learn_preference(self):
        """Test learning a preference."""
        user_id = "test_user"
        
        pref = self.learner.learn_preference(
            user_id=user_id,
            key="test_pref",
            value="test_value",
            source="explicit",
        )
        
        self.assertEqual(pref.confidence, 0.4)
        self.assertEqual(pref.mention_count, 1)
        
        # Learn again to boost confidence
        pref2 = self.learner.learn_preference(
            user_id=user_id,
            key="test_pref",
            value="test_value",
        )
        
        self.assertGreater(pref2.confidence, pref.confidence)
        self.assertEqual(pref2.mention_count, 2)
    
    def test_learn_from_message(self):
        """Test learning from a complete message."""
        user_id = "test_user"
        text = "Ich mochte es bei 21 Grad und stehe um 7:00 auf"
        
        learned = self.learner.learn_from_message(user_id, text)
        
        self.assertGreater(len(learned), 0)
        
        # Verify stored
        prefs = self.learner.get_user_preferences(user_id)
        self.assertGreater(len(prefs), 0)
    
    def test_get_user_preferences(self):
        """Test retrieving user preferences."""
        user_id = "test_user"
        
        self.learner.learn_preference(user_id, "pref1", "value1")
        self.learner.learn_preference(user_id, "pref2", "value2")
        
        prefs = self.learner.get_user_preferences(user_id)
        
        self.assertEqual(len(prefs), 2)
    
    def test_get_preference(self):
        """Test getting a specific preference."""
        user_id = "test_user"
        
        self.learner.learn_preference(user_id, "specific_key", "specific_value")
        
        pref = self.learner.get_preference(user_id, "specific_key")
        
        self.assertIsNotNone(pref)
        self.assertEqual(pref.value, "specific_value")
    
    def test_update_preference(self):
        """Test updating a preference."""
        user_id = "test_user"
        
        self.learner.learn_preference(user_id, "update_key", "old_value")
        
        updated = self.learner.update_preference(
            user_id, "update_key", "new_value", confidence=0.9
        )
        
        self.assertEqual(updated.value, "new_value")
        self.assertEqual(updated.confidence, 0.9)
    
    def test_delete_preference(self):
        """Test deleting a preference."""
        user_id = "test_user"
        
        self.learner.learn_preference(user_id, "delete_key", "value")
        
        result = self.learner.delete_preference(user_id, "delete_key")
        
        self.assertTrue(result)
        self.assertIsNone(self.learner.get_preference(user_id, "delete_key"))
    
    def test_delete_all_user_preferences(self):
        """Test deleting all preferences for a user."""
        user_id = "test_user"
        
        self.learner.learn_preference(user_id, "key1", "value1")
        self.learner.learn_preference(user_id, "key2", "value2")
        self.learner.learn_preference(user_id, "key3", "value3")
        
        count = self.learner.delete_all_user_preferences(user_id)
        
        self.assertEqual(count, 3)
        
        prefs = self.learner.get_user_preferences(user_id)
        self.assertEqual(len(prefs), 0)
    
    def test_confidence_boost(self):
        """Test confidence increases with repetition."""
        user_id = "test_user"
        
        # First mention
        pref1 = self.learner.learn_preference(user_id, "repeat_key", "value")
        conf1 = pref1.confidence
        
        # Second mention
        pref2 = self.learner.learn_preference(user_id, "repeat_key", "value")
        conf2 = pref2.confidence
        
        # Third mention
        pref3 = self.learner.learn_preference(user_id, "repeat_key", "value")
        conf3 = pref3.confidence
        
        self.assertLess(conf1, conf2)
        self.assertLess(conf2, conf3)
        self.assertLessEqual(conf3, 1.0)
    
    def test_get_preferences_for_prompt(self):
        """Test formatting preferences for LLM prompt."""
        user_id = "test_user"
        
        self.learner.learn_preference(user_id, "temp", "22", source="explicit")
        self.learner.learn_preference(user_id, "wake", "06:30", source="inferred")
        
        # Low confidence should not appear
        prompt = self.learner.get_preferences_for_prompt(user_id)
        
        self.assertIn("temp", prompt)
        self.assertIn("*", prompt)  # explicit marker
    
    def test_export_user_preferences(self):
        """Test GDPR export of preferences."""
        user_id = "test_user"
        
        self.learner.learn_preference(user_id, "export_key", "export_value")
        
        export = self.learner.export_user_preferences(user_id)
        
        self.assertIsNotNone(export)
        self.assertEqual(export["user_id"], user_id)
        self.assertGreater(export["count"], 0)
    
    def test_get_stats(self):
        """Test getting learning statistics."""
        user_id = "test_user"
        
        self.learner.learn_preference(user_id, "stat_key", "value")
        
        stats = self.learner.get_stats()
        
        self.assertIn("total_preferences", stats)
        self.assertIn("unique_users", stats)
        self.assertGreater(stats["total_preferences"], 0)


if __name__ == "__main__":
    unittest.main()
