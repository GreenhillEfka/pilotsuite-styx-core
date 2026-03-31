"""Tests for ZoneTruthStore — Canonical zone topology storage."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import os

REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)

from copilot_core.storage.zone_truth import (
    ZoneTruthStore,
    ZoneDefinitionV1,
    ZoneArchetypeV1,
    ZoneEntityAssignmentV1,
    get_zone_truth_store,
    reset_zone_truth_store,
)


class TestZoneEntityAssignmentV1:
    """Tests for ZoneEntityAssignmentV1 dataclass."""

    def test_create_assignment(self) -> None:
        """Test creating an entity assignment."""
        assignment = ZoneEntityAssignmentV1(
            entity_id="light.wohnzimmer_hauptlicht",
            role="lights",
            tags=["licht", "styx"],
            display_name="Hauptlicht",
            source="manual",
        )
        
        assert assignment.entity_id == "light.wohnzimmer_hauptlicht"
        assert assignment.role == "lights"
        assert assignment.tags == ["licht", "styx"]
        assert assignment.display_name == "Hauptlicht"
        assert assignment.source == "manual"

    def test_assignment_to_dict_roundtrip(self) -> None:
        """Test serialization and deserialization."""
        original = ZoneEntityAssignmentV1(
            entity_id="sensor.kitchen_motion",
            role="motion",
            tags=["bewegung", "sensor"],
            source="ha_sync",
        )
        
        data = original.to_dict()
        restored = ZoneEntityAssignmentV1.from_dict(data)
        
        assert restored.entity_id == original.entity_id
        assert restored.role == original.role
        assert restored.tags == original.tags
        assert restored.source == original.source


class TestZoneDefinitionV1:
    """Tests for ZoneDefinitionV1 dataclass."""

    def test_create_zone_definition(self) -> None:
        """Test creating a zone definition."""
        zone = ZoneDefinitionV1(
            zone_id="wohnzimmer",
            name="Wohnzimmer",
            zone_type="living",
            icon="mdi:sofa",
            priority=10,
        )
        
        assert zone.zone_id == "wohnzimmer"
        assert zone.name == "Wohnzimmer"
        assert zone.zone_type == "living"
        assert zone.icon == "mdi:sofa"
        assert zone.priority == 10
        assert zone.revision == 0

    def test_zone_definition_with_entities(self) -> None:
        """Test zone definition with entity assignments."""
        zone = ZoneDefinitionV1(
            zone_id="kitchen",
            name="Küche",
            zone_type="kitchen",
        )
        
        zone.add_entity("light.kitchen_ceiling", "lights", ["licht"])
        zone.add_entity("binary_sensor.kitchen_motion", "motion", ["bewegung"])
        
        assert len(zone.entities) == 2
        by_role = zone.get_entities_by_role()
        assert "lights" in by_role
        assert "motion" in by_role
        assert len(by_role["lights"]) == 1
        assert len(by_role["motion"]) == 1

    def test_zone_definition_touch_increments_revision(self) -> None:
        """Test that touch() increments revision."""
        zone = ZoneDefinitionV1(
            zone_id="test",
            name="Test",
            zone_type="living",
        )
        
        assert zone.revision == 0
        zone.touch()
        assert zone.revision == 1
        zone.touch()
        assert zone.revision == 2

    def test_zone_definition_to_dict_roundtrip(self) -> None:
        """Test serialization and deserialization."""
        original = ZoneDefinitionV1(
            zone_id="terrace",
            name="Terrasse",
            zone_type="terrace",
            icon="mdi:balcony",
            priority=5,
            enabled_modules={"light", "camera"},
            ha_area_id="terrace_area",
        )
        original.add_entity("light.balkon", "lights", source="ha_sync")
        
        data = original.to_dict()
        restored = ZoneDefinitionV1.from_dict(data)
        
        assert restored.zone_id == original.zone_id
        assert restored.name == original.name
        assert restored.zone_type == original.zone_type
        assert restored.icon == original.icon
        assert restored.priority == original.priority
        assert restored.enabled_modules == original.enabled_modules
        assert restored.ha_area_id == original.ha_area_id
        assert len(restored.entities) == len(original.entities)


class TestZoneArchetypeV1:
    """Tests for ZoneArchetypeV1 dataclass."""

    def test_create_archetype(self) -> None:
        """Test creating a zone archetype."""
        archetype = ZoneArchetypeV1(
            zone_type="living",
            name_template="{name} Bereich",
            description="Living area archetype",
            default_modules={"light", "motion", "climate"},
            default_icon="mdi:sofa",
            default_priority=10,
            expected_roles=["lights", "motion", "climate"],
        )
        
        assert archetype.zone_type == "living"
        assert archetype.default_modules == {"light", "motion", "climate"}
        assert len(archetype.expected_roles) == 3


class TestZoneTruthStore:
    """Tests for ZoneTruthStore."""

    def test_create_store(self) -> None:
        """Test creating a store."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ZoneTruthStore(
                persist=True,
                storage_path=os.path.join(tmpdir, "zone_truth.json"),
            )
            
            assert store.get_all_zones() == []
            assert store.get_current_revision() == 0

    def test_create_zone(self) -> None:
        """Test creating a zone."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ZoneTruthStore(
                persist=True,
                storage_path=os.path.join(tmpdir, "zone_truth.json"),
            )
            
            zone = store.create_zone(
                zone_id="wohnzimmer",
                name="Wohnzimmer",
                zone_type="living",
                icon="mdi:sofa",
                priority=10,
                enabled_modules={"light", "motion"},
            )
            
            assert zone.zone_id == "wohnzimmer"
            assert zone.name == "Wohnzimmer"
            assert zone.zone_type == "living"
            assert zone.revision == 1
            
            # Check revision history
            history = store.get_revision_history()
            assert len(history) == 1
            assert history[0].change_type == "created"
            assert history[0].zone_id == "wohnzimmer"

    def test_update_zone(self) -> None:
        """Test updating a zone."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ZoneTruthStore(
                persist=True,
                storage_path=os.path.join(tmpdir, "zone_truth.json"),
            )
            
            store.create_zone("test", "Test", "living")
            zone = store.update_zone("test", name="Updated Test", priority=20)
            
            assert zone.name == "Updated Test"
            assert zone.priority == 20
            assert zone.revision == 2

    def test_delete_zone(self) -> None:
        """Test deleting a zone."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ZoneTruthStore(
                persist=True,
                storage_path=os.path.join(tmpdir, "zone_truth.json"),
            )
            
            store.create_zone("test", "Test", "living")
            assert store.get_zone("test") is not None
            
            result = store.delete_zone("test")
            assert result is True
            assert store.get_zone("test") is None

    def test_add_entity(self) -> None:
        """Test adding an entity to a zone."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ZoneTruthStore(
                persist=True,
                storage_path=os.path.join(tmpdir, "zone_truth.json"),
            )
            
            store.create_zone("kitchen", "Küche", "kitchen")
            assignment = store.add_entity(
                zone_id="kitchen",
                entity_id="light.kitchen_ceiling",
                role="lights",
                tags=["licht"],
                source="ha_sync",
            )
            
            assert assignment.entity_id == "light.kitchen_ceiling"
            assert assignment.role == "lights"
            assert assignment.source == "ha_sync"
            
            zone = store.get_zone("kitchen")
            assert len(zone.entities) == 1

    def test_remove_entity(self) -> None:
        """Test removing an entity from a zone."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ZoneTruthStore(
                persist=True,
                storage_path=os.path.join(tmpdir, "zone_truth.json"),
            )
            
            store.create_zone("test", "Test", "living")
            store.add_entity("test", "light.test", "lights")
            
            result = store.remove_entity("test", "light.test")
            assert result is True
            
            zone = store.get_zone("test")
            assert len(zone.entities) == 0

    def test_sync_zones_create_and_update(self) -> None:
        """Test syncing zones from HA."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ZoneTruthStore(
                persist=True,
                storage_path=os.path.join(tmpdir, "zone_truth.json"),
            )
            
            # Initial sync
            zones_payload = [
                {
                    "zone_id": "wohnzimmer",
                    "name": "Wohnzimmer",
                    "zone_type": "living",
                    "entities": [
                        {"entity_id": "light.wohnzimmer_hauptlicht", "role": "lights"},
                        {"entity_id": "sensor.wohnzimmer_temp", "role": "sensors"},
                    ],
                    "enabled_modules": ["light", "motion"],
                    "ha_area_id": "wohnzimmer_area",
                }
            ]
            
            result = store.sync_zones(zones_payload, source="ha_sync")
            
            assert result["synced"] == 1
            assert result["created"] == 1
            assert result["updated"] == 0
            assert "wohnzimmer" in result["zone_ids"]
            
            zone = store.get_zone("wohnzimmer")
            assert zone is not None
            assert zone.name == "Wohnzimmer"
            assert zone.zone_type == "living"
            assert zone.ha_area_id == "wohnzimmer_area"
            assert len(zone.entities) == 2
            assert zone.enabled_modules == {"light", "motion"}
            
            # Second sync (update)
            zones_payload = [
                {
                    "zone_id": "wohnzimmer",
                    "name": "Wohnzimmer Updated",
                    "zone_type": "living",
                    "entities": [
                        {"entity_id": "light.wohnzimmer_hauptlicht", "role": "lights"},
                    ],
                }
            ]
            
            result = store.sync_zones(zones_payload, source="ha_sync")
            
            assert result["updated"] == 1
            zone = store.get_zone("wohnzimmer")
            assert zone.name == "Wohnzimmer Updated"

    def test_sync_zones_full_sync_deletes_missing(self) -> None:
        """Test that full_sync deletes zones not in payload."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ZoneTruthStore(
                persist=True,
                storage_path=os.path.join(tmpdir, "zone_truth.json"),
            )
            
            # Create two zones
            store.create_zone("zone_a", "Zone A", "living")
            store.create_zone("zone_b", "Zone B", "bedroom")
            
            # Full sync with only zone_a
            zones_payload = [
                {
                    "zone_id": "zone_a",
                    "name": "Zone A",
                    "zone_type": "living",
                }
            ]
            
            result = store.sync_zones(zones_payload, full_sync=True, source="ha_sync")
            
            assert result["deleted"] == 1
            assert store.get_zone("zone_a") is not None
            assert store.get_zone("zone_b") is None

    def test_get_entities_by_role(self) -> None:
        """Test getting entities grouped by role."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ZoneTruthStore(
                persist=True,
                storage_path=os.path.join(tmpdir, "zone_truth.json"),
            )
            
            store.create_zone("kitchen", "Küche", "kitchen")
            store.add_entity("kitchen", "light.kitchen", "lights")
            store.add_entity("kitchen", "light.kitchen_stripe", "lights")
            store.add_entity("kitchen", "binary_sensor.kitchen_motion", "motion")
            
            by_role = store.get_entities_by_role("kitchen")
            
            assert "lights" in by_role
            assert "motion" in by_role
            assert len(by_role["lights"]) == 2
            assert len(by_role["motion"]) == 1

    def test_get_all_entities_read_model(self) -> None:
        """Test getting read-model for all entities."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ZoneTruthStore(
                persist=True,
                storage_path=os.path.join(tmpdir, "zone_truth.json"),
            )
            
            store.create_zone("zone_a", "Zone A", "living")
            store.create_zone("zone_b", "Zone B", "bedroom")
            
            store.add_entity("zone_a", "light.a1", "lights")
            store.add_entity("zone_b", "light.b1", "lights")
            store.add_entity("zone_b", "sensor.b1", "sensors")
            
            model = store.get_all_entities_read_model()
            
            assert model["summary"]["zone_count"] == 2
            assert model["summary"]["entity_count"] == 3
            assert len(model["zones"]) == 2

    def test_get_all_entities_read_model_deltas(self) -> None:
        """Test delta queries for read-model."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ZoneTruthStore(
                persist=True,
                storage_path=os.path.join(tmpdir, "zone_truth.json"),
            )
            
            store.create_zone("zone_a", "Zone A", "living")
            store.add_entity("zone_a", "light.a1", "lights")
            
            # Get initial revision
            initial = store.get_all_entities_read_model()
            initial_revision = initial["summary"]["revision"]
            
            # Make a change
            store.add_entity("zone_a", "light.a2", "lights")
            
            # Query deltas since initial revision
            deltas = store.get_all_entities_read_model(
                since_revision=initial_revision,
                deltas=True,
            )
            
            # Delta response includes zone count in summary
            assert len(deltas["zones"]) == 1
            assert "delta" in deltas
            assert deltas["delta"]["enabled"] is True

    def test_get_all_entities_read_model_compact(self) -> None:
        """Test compact read-model (no entity details)."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ZoneTruthStore(
                persist=True,
                storage_path=os.path.join(tmpdir, "zone_truth.json"),
            )
            
            store.create_zone("test", "Test", "living")
            store.add_entity("test", "light.test", "lights")
            
            model = store.get_all_entities_read_model(compact=True)
            
            assert model["summary"]["compact"] is True
            # Compact mode should not include full entity details
            for zone in model["zones"]:
                assert "entities" not in zone
                assert "entity_count" in zone

    def test_revision_history(self) -> None:
        """Test revision history tracking."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ZoneTruthStore(
                persist=True,
                storage_path=os.path.join(tmpdir, "zone_truth.json"),
            )
            
            store.create_zone("test", "Test", "living")
            store.update_zone("test", name="Updated")
            store.add_entity("test", "light.test", "lights")
            
            history = store.get_revision_history(limit=10)
            
            assert len(history) == 3
            assert history[0].change_type == "created"
            assert history[1].change_type == "updated"
            assert history[2].change_type == "entity_added"

    def test_revision_history_filtered_by_zone(self) -> None:
        """Test revision history filtered by zone."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ZoneTruthStore(
                persist=True,
                storage_path=os.path.join(tmpdir, "zone_truth.json"),
            )
            
            store.create_zone("zone_a", "Zone A", "living")
            store.create_zone("zone_b", "Zone B", "bedroom")
            store.update_zone("zone_a", name="Updated A")
            
            history_a = store.get_revision_history(zone_id="zone_a")
            history_b = store.get_revision_history(zone_id="zone_b")
            
            assert len(history_a) == 2  # created + updated
            assert len(history_b) == 1  # created only

    def test_persistence(self) -> None:
        """Test that data persists to disk."""
        with tempfile.TemporaryDirectory() as tmpdir:
            storage_path = os.path.join(tmpdir, "zone_truth.json")
            
            # Create store and add data
            store1 = ZoneTruthStore(persist=True, storage_path=storage_path)
            store1.create_zone("test", "Test", "living")
            store1.add_entity("test", "light.test", "lights")
            
            # Create new store instance (simulates restart)
            store2 = ZoneTruthStore(persist=True, storage_path=storage_path)
            
            # Data should be loaded from disk
            zone = store2.get_zone("test")
            assert zone is not None
            assert zone.name == "Test"
            assert len(zone.entities) == 1

    def test_archetype_registration(self) -> None:
        """Test registering and retrieving archetypes."""
        with tempfile.TemporaryDirectory() as tmpdir:
            store = ZoneTruthStore(
                persist=True,
                storage_path=os.path.join(tmpdir, "zone_truth.json"),
            )
            
            archetype = ZoneArchetypeV1(
                zone_type="living",
                name_template="{name} Bereich",
                default_modules={"light", "motion"},
            )
            
            store.register_archetype(archetype)
            
            retrieved = store.get_archetype("living")
            assert retrieved is not None
            assert retrieved.zone_type == "living"
            assert retrieved.default_modules == {"light", "motion"}


class TestZoneTruthStoreSingleton:
    """Tests for singleton access pattern."""

    def test_get_zone_truth_store_creates_singleton(self) -> None:
        """Test that get_zone_truth_store creates singleton."""
        # Reset any existing singleton
        reset_zone_truth_store()
        
        store1 = get_zone_truth_store()
        store2 = get_zone_truth_store()
        
        assert store1 is store2
