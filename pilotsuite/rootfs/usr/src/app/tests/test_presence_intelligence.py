"""Tests for Presence Intelligence (v7.1.0)."""

import pytest
from datetime import datetime, timedelta, timezone
from copilot_core.hub.presence_intelligence import (
    PresenceIntelligenceEngine,
    PersonState,
    RoomTransition,
    RoomOccupancy,
    PresenceTrigger,
    PresenceIntelligenceDashboard,
)


@pytest.fixture
def engine():
    e = PresenceIntelligenceEngine()
    e.register_room("wohnzimmer", "Wohnzimmer")
    e.register_room("kueche", "Küche")
    e.register_room("schlafzimmer", "Schlafzimmer")
    e.register_room("buero", "Büro")
    return e


@pytest.fixture
def engine_with_persons(engine):
    engine.register_person("alice", "Alice", icon="mdi:account-circle")
    engine.register_person("bob", "Bob")
    return engine


# ── Person management ───────────────────────────────────────────────────────


class TestPersonManagement:
    def test_register_person(self, engine):
        p = engine.register_person("alice", "Alice")
        assert p.person_id == "alice"
        assert p.name == "Alice"
        assert p.is_home is False

    def test_register_duplicate_updates(self, engine):
        engine.register_person("alice", "Alice")
        p = engine.register_person("alice", "Alice Updated", icon="mdi:face")
        assert p.name == "Alice Updated"
        assert p.icon == "mdi:face"

    def test_unregister_person(self, engine):
        engine.register_person("alice", "Alice")
        assert engine.unregister_person("alice") is True
        assert engine.get_person("alice") is None

    def test_unregister_unknown(self, engine):
        assert engine.unregister_person("unknown") is False

    def test_get_person(self, engine_with_persons):
        p = engine_with_persons.get_person("alice")
        assert p is not None
        assert p["name"] == "Alice"
        assert p["icon"] == "mdi:account-circle"

    def test_get_unknown_person(self, engine):
        assert engine.get_person("unknown") is None


# ── Room management ─────────────────────────────────────────────────────────


class TestRoomManagement:
    def test_register_room(self, engine):
        assert len(engine.get_rooms()) == 4

    def test_rooms_start_empty(self, engine):
        rooms = engine.get_rooms()
        for r in rooms:
            assert r["current_count"] == 0

    def test_room_shows_occupants(self, engine_with_persons):
        engine_with_persons.update_presence("alice", "wohnzimmer", is_home=True)
        rooms = engine_with_persons.get_rooms()
        wz = next(r for r in rooms if r["room_id"] == "wohnzimmer")
        assert wz["current_count"] == 1
        assert "alice" in wz["persons"]


# ── Presence updates ────────────────────────────────────────────────────────


class TestPresenceUpdates:
    def test_update_presence_home(self, engine_with_persons):
        assert engine_with_persons.update_presence("alice", "wohnzimmer", is_home=True) is True
        p = engine_with_persons.get_person("alice")
        assert p["is_home"] is True
        assert p["current_room"] == "wohnzimmer"

    def test_update_presence_away(self, engine_with_persons):
        engine_with_persons.update_presence("alice", "wohnzimmer", is_home=True)
        engine_with_persons.update_presence("alice", is_home=False)
        p = engine_with_persons.get_person("alice")
        assert p["is_home"] is False
        assert p["current_room"] == ""

    def test_update_unknown_person(self, engine):
        assert engine.update_presence("unknown", "wohnzimmer") is False

    def test_room_transition(self, engine_with_persons):
        engine_with_persons.update_presence("alice", "wohnzimmer", is_home=True)
        engine_with_persons.update_presence("alice", "kueche", is_home=True)
        transitions = engine_with_persons.get_transitions()
        assert len(transitions) == 1
        assert transitions[0]["from_room"] == "wohnzimmer"
        assert transitions[0]["to_room"] == "kueche"

    def test_multiple_transitions(self, engine_with_persons):
        engine_with_persons.update_presence("alice", "wohnzimmer", is_home=True)
        engine_with_persons.update_presence("alice", "kueche", is_home=True)
        engine_with_persons.update_presence("alice", "buero", is_home=True)
        transitions = engine_with_persons.get_transitions()
        assert len(transitions) == 2

    def test_zone_tracking(self, engine_with_persons):
        engine_with_persons.update_presence("alice", "wohnzimmer", zone_id="eg", is_home=True)
        p = engine_with_persons.get_person("alice")
        assert p["current_zone"] == "eg"

    def test_transitions_capped(self, engine_with_persons):
        engine_with_persons.update_presence("alice", "wohnzimmer", is_home=True)
        for i in range(600):
            room = "kueche" if i % 2 == 0 else "wohnzimmer"
            engine_with_persons.update_presence("alice", room, is_home=True)
        assert len(engine_with_persons._transitions) == 500


# ── Triggers ────────────────────────────────────────────────────────────────


class TestTriggers:
    def test_register_trigger(self, engine):
        assert engine.register_trigger("t1", "arrival") is True
        triggers = engine.get_triggers()
        assert len(triggers) == 1

    def test_register_invalid_type(self, engine):
        assert engine.register_trigger("t1", "invalid") is False

    def test_register_duplicate(self, engine):
        engine.register_trigger("t1", "arrival")
        assert engine.register_trigger("t1", "departure") is False

    def test_unregister_trigger(self, engine):
        engine.register_trigger("t1", "arrival")
        assert engine.unregister_trigger("t1") is True
        assert len(engine.get_triggers()) == 0

    def test_unregister_unknown(self, engine):
        assert engine.unregister_trigger("unknown") is False

    def test_arrival_trigger_fires(self, engine_with_persons):
        engine_with_persons.register_trigger("t_arrive", "arrival", person_id="alice")
        engine_with_persons.update_presence("alice", "wohnzimmer", is_home=True)
        triggers = engine_with_persons.get_triggers()
        t = next(t for t in triggers if t["trigger_id"] == "t_arrive")
        assert t["fired_count"] == 1

    def test_departure_trigger_fires(self, engine_with_persons):
        engine_with_persons.update_presence("alice", "wohnzimmer", is_home=True)
        engine_with_persons.register_trigger("t_depart", "departure", person_id="alice")
        engine_with_persons.update_presence("alice", is_home=False)
        triggers = engine_with_persons.get_triggers()
        t = next(t for t in triggers if t["trigger_id"] == "t_depart")
        assert t["fired_count"] == 1

    def test_room_enter_trigger(self, engine_with_persons):
        engine_with_persons.register_trigger("t_enter_kueche", "room_enter", room_id="kueche")
        engine_with_persons.update_presence("alice", "wohnzimmer", is_home=True)
        engine_with_persons.update_presence("alice", "kueche", is_home=True)
        triggers = engine_with_persons.get_triggers()
        t = next(t for t in triggers if t["trigger_id"] == "t_enter_kueche")
        assert t["fired_count"] == 1

    def test_room_leave_trigger(self, engine_with_persons):
        engine_with_persons.register_trigger("t_leave_wz", "room_leave", room_id="wohnzimmer")
        engine_with_persons.update_presence("alice", "wohnzimmer", is_home=True)
        engine_with_persons.update_presence("alice", "kueche", is_home=True)
        triggers = engine_with_persons.get_triggers()
        t = next(t for t in triggers if t["trigger_id"] == "t_leave_wz")
        assert t["fired_count"] == 1

    def test_idle_trigger(self, engine_with_persons):
        engine_with_persons.register_trigger("t_idle", "idle", idle_threshold_min=0)
        engine_with_persons.update_presence("alice", "wohnzimmer", is_home=True)
        # Simulate time passing
        engine_with_persons._persons["alice"].last_seen = (
            datetime.now(tz=timezone.utc) - timedelta(minutes=1)
        )
        fired = engine_with_persons.check_idle_triggers()
        assert "t_idle" in fired

    def test_trigger_person_filter(self, engine_with_persons):
        engine_with_persons.register_trigger("t_bob_arrive", "arrival", person_id="bob")
        engine_with_persons.update_presence("alice", "wohnzimmer", is_home=True)
        triggers = engine_with_persons.get_triggers()
        t = next(t for t in triggers if t["trigger_id"] == "t_bob_arrive")
        assert t["fired_count"] == 0  # should not fire for alice


# ── Analytics ───────────────────────────────────────────────────────────────


class TestAnalytics:
    def test_room_occupancy(self, engine_with_persons):
        engine_with_persons.update_presence("alice", "wohnzimmer", is_home=True)
        engine_with_persons.update_presence("bob", "wohnzimmer", is_home=True)
        occ = engine_with_persons.get_room_occupancy("wohnzimmer")
        assert isinstance(occ, RoomOccupancy)
        assert occ.current_count == 2
        assert "alice" in occ.persons
        assert "bob" in occ.persons

    def test_room_occupancy_visits(self, engine_with_persons):
        engine_with_persons.update_presence("alice", "wohnzimmer", is_home=True)
        engine_with_persons.update_presence("alice", "kueche", is_home=True)
        engine_with_persons.update_presence("alice", "wohnzimmer", is_home=True)
        occ = engine_with_persons.get_room_occupancy("wohnzimmer")
        assert occ.total_visits == 2  # entered twice

    def test_heatmap(self, engine_with_persons):
        engine_with_persons.update_presence("alice", "wohnzimmer", is_home=True)
        engine_with_persons.update_presence("alice", "kueche", is_home=True)
        heatmap = engine_with_persons.get_heatmap(24)
        assert isinstance(heatmap, list)
        assert len(heatmap) >= 1

    def test_transitions_list(self, engine_with_persons):
        engine_with_persons.update_presence("alice", "wohnzimmer", is_home=True)
        engine_with_persons.update_presence("alice", "kueche", is_home=True)
        t = engine_with_persons.get_transitions(limit=10)
        assert len(t) == 1
        assert t[0]["person_id"] == "alice"


# ── Household status ────────────────────────────────────────────────────────


class TestHouseholdStatus:
    def test_empty_household(self, engine):
        status = engine.get_household_status()
        assert status["status"] == "unknown"

    def test_all_home(self, engine_with_persons):
        engine_with_persons.update_presence("alice", "wohnzimmer", is_home=True)
        engine_with_persons.update_presence("bob", "kueche", is_home=True)
        status = engine_with_persons.get_household_status()
        assert status["status"] == "home"
        assert status["persons_home"] == 2

    def test_all_away(self, engine_with_persons):
        status = engine_with_persons.get_household_status()
        assert status["status"] == "away"
        assert status["persons_away"] == 2

    def test_partial(self, engine_with_persons):
        engine_with_persons.update_presence("alice", "wohnzimmer", is_home=True)
        status = engine_with_persons.get_household_status()
        assert status["status"] == "partial"
        assert status["persons_home"] == 1
        assert status["persons_away"] == 1


# ── Dashboard ───────────────────────────────────────────────────────────────


class TestDashboard:
    def test_dashboard_empty(self, engine):
        db = engine.get_dashboard()
        assert isinstance(db, PresenceIntelligenceDashboard)
        assert db.total_persons == 0
        assert db.total_rooms == 4

    def test_dashboard_with_data(self, engine_with_persons):
        engine_with_persons.update_presence("alice", "wohnzimmer", is_home=True)
        engine_with_persons.register_trigger("t1", "arrival")
        db = engine_with_persons.get_dashboard()
        assert db.total_persons == 2
        assert db.persons_home == 1
        assert db.persons_away == 1
        assert db.occupied_rooms == 1
        assert db.active_triggers == 1
        assert db.household_status == "partial"

    def test_dashboard_transitions(self, engine_with_persons):
        engine_with_persons.update_presence("alice", "wohnzimmer", is_home=True)
        engine_with_persons.update_presence("alice", "kueche", is_home=True)
        db = engine_with_persons.get_dashboard()
        assert len(db.recent_transitions) == 1
