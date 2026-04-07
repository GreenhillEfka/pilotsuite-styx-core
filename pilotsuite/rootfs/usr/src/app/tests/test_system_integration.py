"""Tests for System Integration Hub (v7.3.0)."""

import pytest
from unittest.mock import MagicMock, patch
from copilot_core.hub.system_integration import (
    SystemIntegrationHub,
    IntegrationEvent,
    IntegrationStatus,
)


@pytest.fixture
def hub():
    return SystemIntegrationHub()


@pytest.fixture
def wired_hub():
    h = SystemIntegrationHub()

    # Register mock engines
    h.register_engine("scene_intelligence", MagicMock())
    h.register_engine("media_follow", MagicMock())
    h.register_engine("notification_intelligence", MagicMock())
    h.register_engine("light_intelligence", MagicMock())
    h.register_engine("zone_modes", MagicMock())
    h.register_engine("predictive_maintenance", MagicMock())
    h.register_engine("energy_advisor", MagicMock())
    h.register_engine("presence_intelligence", MagicMock())

    h.auto_wire()
    return h


# ── Engine registration ─────────────────────────────────────────────────────


class TestEngineRegistration:
    def test_register_engine(self, hub):
        engine = MagicMock()
        hub.register_engine("test", engine)
        assert hub.get_engine("test") is engine

    def test_get_unknown_engine(self, hub):
        assert hub.get_engine("unknown") is None

    def test_register_multiple_engines(self, hub):
        hub.register_engine("a", MagicMock())
        hub.register_engine("b", MagicMock())
        status = hub.get_status()
        assert status.engines_connected == 2


# ── Subscriptions ───────────────────────────────────────────────────────────


class TestSubscriptions:
    def test_subscribe(self, hub):
        hub.subscribe("test_event", "engine_a")
        diagram = hub.get_wiring_diagram()
        assert "test_event" in diagram
        assert "engine_a" in diagram["test_event"]

    def test_subscribe_no_duplicates(self, hub):
        hub.subscribe("test_event", "engine_a")
        hub.subscribe("test_event", "engine_a")
        assert len(hub.get_wiring_diagram()["test_event"]) == 1

    def test_unsubscribe(self, hub):
        hub.subscribe("test_event", "engine_a")
        hub.unsubscribe("test_event", "engine_a")
        assert len(hub.get_wiring_diagram().get("test_event", [])) == 0

    def test_unsubscribe_nonexistent(self, hub):
        hub.unsubscribe("nonexistent", "engine_a")  # Should not raise


# ── Auto-wiring ─────────────────────────────────────────────────────────────


class TestAutoWiring:
    def test_auto_wire(self, wired_hub):
        diagram = wired_hub.get_wiring_diagram()
        assert "presence_changed" in diagram
        assert "scene_intelligence" in diagram["presence_changed"]
        assert "media_follow" in diagram["presence_changed"]
        assert "notification_intelligence" in diagram["presence_changed"]

    def test_auto_wire_zone_mode(self, wired_hub):
        diagram = wired_hub.get_wiring_diagram()
        assert "zone_mode_changed" in diagram
        assert "light_intelligence" in diagram["zone_mode_changed"]

    def test_auto_wire_scene(self, wired_hub):
        diagram = wired_hub.get_wiring_diagram()
        assert "scene_activated" in diagram
        assert "zone_modes" in diagram["scene_activated"]

    def test_auto_wire_anomaly(self, wired_hub):
        diagram = wired_hub.get_wiring_diagram()
        assert "anomaly_detected" in diagram
        assert "notification_intelligence" in diagram["anomaly_detected"]
        assert "predictive_maintenance" in diagram["anomaly_detected"]

    def test_auto_wire_count(self, wired_hub):
        status = wired_hub.get_status()
        assert status.active_subscriptions > 0

    def test_auto_wire_skips_missing_engines(self, hub):
        hub.register_engine("scene_intelligence", MagicMock())
        count = hub.auto_wire()
        # Only subscriptions for existing engines
        assert count >= 1


# ── Event dispatch ──────────────────────────────────────────────────────────


class TestDispatch:
    def test_dispatch_basic(self, wired_hub):
        event = wired_hub.dispatch("presence_changed", "presence_intelligence", {
            "person_id": "alice", "is_home": True, "zone_id": "wohnzimmer",
            "hour": 12, "occupancy_count": 1,
        })
        assert isinstance(event, IntegrationEvent)
        assert len(event.handled_by) > 0

    def test_dispatch_skips_source(self, hub):
        hub.register_engine("engine_a", MagicMock())
        hub.subscribe("test", "engine_a")
        event = hub.dispatch("test", "engine_a", {})
        assert "engine_a" not in event.handled_by

    def test_dispatch_no_subscribers(self, hub):
        event = hub.dispatch("unknown_event", "test", {})
        assert len(event.handled_by) == 0

    def test_dispatch_increments_counter(self, wired_hub):
        wired_hub.dispatch("presence_changed", "test", {"is_home": True})
        wired_hub.dispatch("presence_changed", "test", {"is_home": False})
        assert wired_hub._events_processed == 2

    def test_dispatch_logs_events(self, wired_hub):
        wired_hub.dispatch("presence_changed", "test", {"is_home": True})
        status = wired_hub.get_status()
        assert len(status.event_log) > 0
        assert status.last_event == "presence_changed"

    def test_dispatch_event_log_capped(self, hub):
        hub.register_engine("e", MagicMock())
        hub.subscribe("test", "e")
        for i in range(250):
            hub.dispatch("test", "source", {"i": i})
        assert len(hub._event_log) == 200


# ── Presence events ─────────────────────────────────────────────────────────


class TestPresenceEvents:
    def test_presence_triggers_scene_suggest(self, wired_hub):
        scene_engine = wired_hub.get_engine("scene_intelligence")
        wired_hub.dispatch("presence_changed", "presence", {
            "person_id": "alice", "is_home": True,
            "zone_id": "wohnzimmer", "hour": 8, "occupancy_count": 1,
        })
        assert scene_engine.suggest_scenes.called

    def test_presence_triggers_media_follow(self, wired_hub):
        media_engine = wired_hub.get_engine("media_follow")
        wired_hub.dispatch("presence_changed", "presence", {
            "person_id": "alice", "is_home": True, "zone_id": "kueche",
        })
        assert media_engine.on_zone_enter.called

    def test_presence_triggers_notification(self, wired_hub):
        notif_engine = wired_hub.get_engine("notification_intelligence")
        wired_hub.dispatch("presence_changed", "presence", {
            "person_id": "alice", "is_home": True,
        })
        assert notif_engine.send.called


# ── Zone mode events ────────────────────────────────────────────────────────


class TestZoneModeEvents:
    def test_zone_mode_triggers_light(self, wired_hub):
        light_engine = wired_hub.get_engine("light_intelligence")
        wired_hub.dispatch("zone_mode_changed", "zone_modes", {
            "zone_id": "wohnzimmer", "mode_id": "movie",
        })
        assert light_engine.set_active_scene.called

    def test_zone_mode_triggers_dnd(self, wired_hub):
        notif_engine = wired_hub.get_engine("notification_intelligence")
        wired_hub.dispatch("zone_mode_changed", "zone_modes", {
            "zone_id": "wz", "mode_id": "night",
        })
        notif_engine.set_dnd.assert_called_once_with(enabled=True, zone_mode="night")


# ── Scene events ────────────────────────────────────────────────────────────


class TestSceneEvents:
    def test_scene_activates_zone_mode(self, wired_hub):
        mode_engine = wired_hub.get_engine("zone_modes")
        wired_hub.dispatch("scene_activated", "scene_intelligence", {
            "zone_id": "wz",
            "scene": {"name_de": "Party", "zone_mode": "party", "suppress_automations": True},
        })
        mode_engine.activate_mode.assert_called_once_with(zone_id="wz", mode_id="party")

    def test_scene_triggers_notification(self, wired_hub):
        notif_engine = wired_hub.get_engine("notification_intelligence")
        wired_hub.dispatch("scene_activated", "scene_intelligence", {
            "scene": {"name_de": "Filmabend", "suppress_automations": True},
        })
        assert notif_engine.send.called
        assert notif_engine.set_dnd.called


# ── Anomaly events ──────────────────────────────────────────────────────────


class TestAnomalyEvents:
    def test_anomaly_triggers_notification(self, wired_hub):
        notif_engine = wired_hub.get_engine("notification_intelligence")
        wired_hub.dispatch("anomaly_detected", "anomaly_detection", {
            "entity_id": "sensor.temp", "severity": "high",
            "message": "Temperature spike detected",
        })
        assert notif_engine.send.called
        call_kwargs = notif_engine.send.call_args
        assert call_kwargs[1]["priority"] == "high"

    def test_anomaly_triggers_maintenance(self, wired_hub):
        maint_engine = wired_hub.get_engine("predictive_maintenance")
        wired_hub.dispatch("anomaly_detected", "anomaly_detection", {
            "entity_id": "sensor.battery", "severity": "critical",
        })
        assert maint_engine.evaluate_all.called


# ── Energy events ───────────────────────────────────────────────────────────


class TestEnergyEvents:
    def test_energy_threshold_notification(self, wired_hub):
        notif_engine = wired_hub.get_engine("notification_intelligence")
        wired_hub.dispatch("energy_threshold", "energy_advisor", {
            "daily_kwh": 25.5,
        })
        assert notif_engine.send.called


# ── Person arrive/depart events ─────────────────────────────────────────────


class TestPersonEvents:
    def test_person_arrived_suggests_scene(self, wired_hub):
        scene_engine = wired_hub.get_engine("scene_intelligence")
        wired_hub.dispatch("person_arrived", "presence", {
            "person_id": "alice", "hour": 18, "occupancy_count": 1,
        })
        assert scene_engine.suggest_scenes.called

    def test_person_departed_away_scene(self, wired_hub):
        scene_engine = wired_hub.get_engine("scene_intelligence")
        wired_hub.dispatch("person_departed", "presence", {
            "person_id": "alice", "occupancy_count": 0,
        })
        scene_engine.activate_scene.assert_called_once_with("away")


# ── Status ──────────────────────────────────────────────────────────────────


class TestStatus:
    def test_status_empty(self, hub):
        status = hub.get_status()
        assert isinstance(status, IntegrationStatus)
        assert status.engines_connected == 0
        assert status.events_processed == 0

    def test_status_with_engines(self, wired_hub):
        status = wired_hub.get_status()
        assert status.engines_connected == 8
        assert "scene_intelligence" in status.engine_names

    def test_wiring_diagram(self, wired_hub):
        diagram = wired_hub.get_wiring_diagram()
        assert isinstance(diagram, dict)
        assert len(diagram) > 0
