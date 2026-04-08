"""Tests for Habitus-Zonen Engine (v6.4.0)."""

import pytest

from copilot_core.hub.habitus_zones import (
    HabitusZone,
    HabitusZoneEngine,
    ZoneOverview,
    ZoneState,
    _ZONE_MODES,
    _ZONE_TEMPLATES,
)


@pytest.fixture
def engine():
    return HabitusZoneEngine()


@pytest.fixture
def populated_engine():
    e = HabitusZoneEngine()
    # Register rooms
    e.register_room("bad", "Bad", entities=[
        "sensor.bad_temperature", "sensor.bad_humidity",
        "light.bad_decke", "binary_sensor.bad_motion",
    ])
    e.register_room("toilette", "Toilette", entities=[
        "light.toilette_licht", "binary_sensor.toilette_motion",
    ])
    e.register_room("wohnzimmer", "Wohnzimmer", entities=[
        "sensor.wohnzimmer_temperature", "light.wohnzimmer_haupt",
        "light.wohnzimmer_stehlampe", "media_player.wohnzimmer_tv",
    ])
    e.register_room("kueche", "Küche", entities=[
        "sensor.kueche_temperature", "light.kueche_decke",
    ])
    # Create zones
    e.create_zone("badbereich", "Badbereich", ["bad", "toilette"], icon="mdi:shower-head")
    e.create_zone("wohnbereich", "Wohnbereich", ["wohnzimmer"], icon="mdi:sofa")
    return e


class TestRoomManagement:
    def test_register_room(self, engine):
        room = engine.register_room("bad", "Bad", entities=["light.bad"])
        assert room.room_id == "bad"
        assert room.name == "Bad"
        assert len(room.entities) == 1

    def test_get_room(self, engine):
        engine.register_room("bad", "Bad", entities=["light.bad"])
        room = engine.get_room("bad")
        assert room is not None
        assert room["name"] == "Bad"
        assert room["entity_count"] == 1

    def test_get_nonexistent_room(self, engine):
        assert engine.get_room("nonexistent") is None

    def test_get_rooms(self, populated_engine):
        rooms = populated_engine.get_rooms()
        assert len(rooms) == 4

    def test_update_room_entities(self, engine):
        engine.register_room("bad", "Bad", entities=["light.bad"])
        result = engine.update_room_entities("bad", ["light.bad", "sensor.bad_temp"])
        assert result is True
        room = engine.get_room("bad")
        assert room["entity_count"] == 2

    def test_update_nonexistent_room(self, engine):
        assert engine.update_room_entities("fake", ["light.x"]) is False

    def test_room_zone_assignment(self, populated_engine):
        room = populated_engine.get_room("bad")
        assert room["zone"] == "badbereich"

    def test_unassigned_room(self, populated_engine):
        room = populated_engine.get_room("kueche")
        assert room["zone"] is None


class TestZoneManagement:
    def test_create_zone(self, engine):
        engine.register_room("r1", "Room 1", entities=["light.r1"])
        zone = engine.create_zone("z1", "Zone 1", ["r1"])
        assert zone.zone_id == "z1"
        assert zone.name == "Zone 1"
        assert len(zone.rooms) == 1
        assert "light.r1" in zone.entities

    def test_zone_entity_adoption(self, populated_engine):
        zone = populated_engine._zones["badbereich"]
        # Should have entities from both Bad and Toilette
        assert "light.bad_decke" in zone.entities
        assert "light.toilette_licht" in zone.entities
        assert len(zone.entities) == 6  # 4 from bad + 2 from toilette

    def test_add_room_to_zone(self, populated_engine):
        result = populated_engine.add_room_to_zone("wohnbereich", "kueche")
        assert result is True
        zone = populated_engine._zones["wohnbereich"]
        assert "kueche" in zone.rooms
        assert "light.kueche_decke" in zone.entities

    def test_add_room_already_in_zone(self, populated_engine):
        result = populated_engine.add_room_to_zone("badbereich", "bad")
        assert result is True  # no error, already assigned

    def test_add_invalid_room(self, populated_engine):
        assert populated_engine.add_room_to_zone("badbereich", "fake") is False

    def test_remove_room_from_zone(self, populated_engine):
        result = populated_engine.remove_room_from_zone("badbereich", "toilette")
        assert result is True
        zone = populated_engine._zones["badbereich"]
        assert "toilette" not in zone.rooms
        assert "light.toilette_licht" not in zone.entities

    def test_delete_zone(self, populated_engine):
        assert populated_engine.delete_zone("badbereich") is True
        assert "badbereich" not in populated_engine._zones

    def test_delete_nonexistent_zone(self, engine):
        assert engine.delete_zone("fake") is False

    def test_get_zone(self, populated_engine):
        zone = populated_engine.get_zone("badbereich")
        assert zone is not None
        assert zone["name"] == "Badbereich"
        assert zone["room_count"] == 2
        assert zone["entity_count"] == 6
        assert len(zone["rooms"]) == 2

    def test_get_nonexistent_zone(self, engine):
        assert engine.get_zone("fake") is None


class TestZoneModes:
    def test_set_mode(self, populated_engine):
        result = populated_engine.set_zone_mode("badbereich", "party")
        assert result is True
        assert populated_engine._zones["badbereich"].mode == "party"

    def test_set_invalid_mode(self, populated_engine):
        assert populated_engine.set_zone_mode("badbereich", "invalid") is False

    def test_set_mode_nonexistent_zone(self, engine):
        assert engine.set_zone_mode("fake", "active") is False

    def test_set_enabled(self, populated_engine):
        populated_engine.set_zone_enabled("badbereich", False)
        assert populated_engine._zones["badbereich"].enabled is False

    def test_set_settings(self, populated_engine):
        populated_engine.set_zone_settings("badbereich", {"min_temp": 20})
        assert populated_engine._zones["badbereich"].settings["min_temp"] == 20

    def test_all_modes_available(self):
        assert "active" in _ZONE_MODES
        assert "sleeping" in _ZONE_MODES
        assert "party" in _ZONE_MODES
        assert "away" in _ZONE_MODES


class TestZoneState:
    def test_state_with_entities(self, populated_engine):
        # Set entity states
        populated_engine.update_entity_state("sensor.bad_temperature", 22.5)
        populated_engine.update_entity_state("sensor.bad_humidity", 65.0)
        populated_engine.update_entity_state("light.bad_decke", "on")
        populated_engine.update_entity_state("binary_sensor.bad_motion", "on")

        state = populated_engine.get_zone_state("badbereich")
        assert state is not None
        assert state.avg_temperature == 22.5
        assert state.avg_humidity == 65.0
        assert state.light_on_count == 1
        assert state.occupancy is True

    def test_state_without_data(self, populated_engine):
        state = populated_engine.get_zone_state("badbereich")
        assert state is not None
        assert state.avg_temperature is None
        assert state.occupancy is False

    def test_state_nonexistent_zone(self, engine):
        assert engine.get_zone_state("fake") is None

    def test_batch_entity_update(self, populated_engine):
        count = populated_engine.update_entity_states_batch({
            "sensor.bad_temperature": 21.0,
            "sensor.bad_humidity": 60.0,
        })
        assert count == 2


class TestZoneOverview:
    def test_overview(self, populated_engine):
        overview = populated_engine.get_overview()
        assert overview.total_zones == 2
        assert overview.total_rooms == 4
        assert overview.active_zones == 2
        assert len(overview.zones) == 2
        assert len(overview.unassigned_rooms) == 1  # kueche

    def test_empty_overview(self, engine):
        overview = engine.get_overview()
        assert overview.total_zones == 0
        assert overview.total_rooms == 0


class TestTemplates:
    def test_get_templates(self, engine):
        templates = engine.get_templates()
        assert len(templates) == len(_ZONE_TEMPLATES)
        names = [t["name"] for t in templates]
        assert "Badbereich" in names
        assert "Wohnbereich" in names

    def test_create_from_template(self, engine):
        engine.register_room("bad", "Bad", entities=["light.bad"])
        engine.register_room("toilette", "Toilette", entities=["light.wc"])
        zone = engine.create_zone_from_template("badbereich")
        assert zone is not None
        assert zone.name == "Badbereich"
        assert "bad" in zone.rooms
        assert "toilette" in zone.rooms

    def test_create_from_invalid_template(self, engine):
        assert engine.create_zone_from_template("nonexistent") is None

    def test_get_modes(self, engine):
        modes = engine.get_modes()
        assert len(modes) == len(_ZONE_MODES)


class TestEntityDeduplication:
    def test_no_duplicate_entities(self, engine):
        engine.register_room("r1", "R1", entities=["light.shared", "sensor.temp"])
        engine.register_room("r2", "R2", entities=["light.shared", "sensor.humid"])
        zone = engine.create_zone("z1", "Z1", ["r1", "r2"])
        assert zone.entities.count("light.shared") == 1
        assert len(zone.entities) == 3  # shared + temp + humid


class TestRoomZoneRefresh:
    def test_entity_refresh_on_room_update(self, populated_engine):
        # Add new entity to bad
        populated_engine.update_room_entities("bad", [
            "sensor.bad_temperature", "sensor.bad_humidity",
            "light.bad_decke", "binary_sensor.bad_motion",
            "switch.bad_heizung",  # new
        ])
        zone = populated_engine._zones["badbereich"]
        assert "switch.bad_heizung" in zone.entities
