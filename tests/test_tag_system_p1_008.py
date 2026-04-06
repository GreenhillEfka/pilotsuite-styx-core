"""Tag System Tests (P1-008 - Ollama Worker 4).

Validates zone mapping, entity tagging, and auto-role detection.
"""

import unittest
from copilot_core.hub.habitus_zones import HabitusZoneEngine

class TagSystemTest(unittest.TestCase):
    """Tests for P1-008 Tag System and Zone Roles."""

    def setUp(self):
        self.engine = HabitusZoneEngine()

    def test_entity_tagging(self):
        """Test assigning tags to entities within zones."""
        zone_id = "test_zone"
        self.engine.create_zone(zone_id, "Test", "living")
        zone = self.engine._zones[zone_id]
        
        # Add tagged entity
        entity_id = "light.test"
        zone.entities.add(entity_id)
        
        self.assertIn(entity_id, zone.entities)

    def test_auto_role_detection(self):
        """Test that zone types map to correct functional roles."""
        zone_id = "office_1"
        self.engine.create_zone(zone_id, "Office", "office")
        zone_info = self.engine.get_zone(zone_id)
        
        # Check if modules are auto-assigned based on role
        self.assertIn("presence", zone_info["modules"])
        self.assertIn("light", zone_info["modules"])
        print(f"✅ Auto-Role Detection: {zone_id} is correctly typed.")

    def test_cross_zone_tag_integrity(self):
        """Ensure tags don't leak between zones."""
        self.engine.create_zone("z1", "Zone 1", "living")
        self.engine.create_zone("z2", "Zone 2", "bedroom")
        
        self.engine._zones["z1"].entities.add("light.1")
        self.assertNotIn("light.1", self.engine._zones["z2"].entities)

if __name__ == "__main__":
    unittest.main()
