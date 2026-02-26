from __future__ import annotations

import os

from flask import Flask

from copilot_core.hub import api as hub_api


def test_build_habitus_recommendations_marks_camera_and_standard_metrics():
    states = [
        {
            "entity_id": "camera.wohnzimmer_cam",
            "attributes": {"friendly_name": "Wohnzimmer Cam", "area_id": "wohnzimmer"},
        },
        {
            "entity_id": "binary_sensor.wohnzimmer_bewegung",
            "attributes": {"friendly_name": "Wohnzimmer Bewegung"},
        },
        {
            "entity_id": "sensor.wohnzimmer_helligkeit",
            "attributes": {"friendly_name": "Wohnzimmer Helligkeit"},
        },
    ]

    zones = hub_api._build_habitus_recommendations(states)
    wohn = next((z for z in zones if z["zone_id"] == "zone:wohnbereich"), None)
    assert wohn is not None

    roles = wohn.get("entity_roles", {})
    assert "camera" in roles
    assert "motion" in roles
    assert "brightness" in roles
    assert wohn["standard_metrics_present"]["camera"] is True
    assert "room:wohnzimmer" in wohn.get("room_ids", [])
    assert any(c.get("room_id") == "room:wohnzimmer" for c in wohn.get("room_candidates", []))


def test_build_habitus_recommendations_supports_multi_room_candidates():
    states = [
        {
            "entity_id": "light.wohnzimmer_decke",
            "attributes": {"friendly_name": "Wohnzimmer Decke", "area_id": "wohnzimmer"},
        },
        {
            "entity_id": "light.wohnflur_decke",
            "attributes": {"friendly_name": "Wohnflur Decke", "area_id": "wohnflur"},
        },
        {
            "entity_id": "media_player.tv_wohnzimmer",
            "attributes": {"friendly_name": "TV Wohnzimmer"},
        },
    ]

    zones = hub_api._build_habitus_recommendations(states)
    wohn = next((z for z in zones if z["zone_id"] == "zone:wohnbereich"), None)
    assert wohn is not None
    room_ids = wohn.get("room_ids", [])
    assert "room:wohnzimmer" in room_ids
    assert "room:wohnflur" in room_ids
    candidates = {c["room_id"]: c for c in wohn.get("room_candidates", [])}
    assert candidates["room:wohnzimmer"]["entity_count"] >= 1
    assert candidates["room:wohnflur"]["entity_count"] >= 1


def test_infer_neuron_tags_has_expected_defaults():
    tags = hub_api._infer_neuron_tags("binary_sensor.motion_flur:on", "light.flur:on")
    assert "context.presence" in tags
    assert "context.light_level" in tags

    fallback = hub_api._infer_neuron_tags("foo", "bar")
    assert fallback == ["context.activity"]


def test_fetch_supervisor_states_external_ha_fallback(monkeypatch):
    class FakeResp:
        def __init__(self, ok: bool, payload):
            self.ok = ok
            self._payload = payload

        def json(self):
            return self._payload

    calls: list[str] = []

    def fake_get(url, headers=None, timeout=0):
        calls.append(url)
        if url.endswith("/states") and "supervisor" in url:
            return FakeResp(False, {})
        if url.endswith("/api/states"):
            return FakeResp(True, [{"entity_id": "light.test"}])
        return FakeResp(False, {})

    monkeypatch.setenv("SUPERVISOR_TOKEN", "sup-token")
    monkeypatch.setenv("SUPERVISOR_API", "http://supervisor/core/api")
    monkeypatch.setenv("HA_TOKEN", "ha-token")
    monkeypatch.setenv("HA_URL", "http://ha.local:8123")
    monkeypatch.setattr(hub_api.requests, "get", fake_get)
    monkeypatch.setattr(hub_api, "_SUPERVISOR_API", os.environ["SUPERVISOR_API"])
    monkeypatch.setattr(hub_api, "_EXTERNAL_HA_API", os.environ["HA_URL"])

    states = hub_api._fetch_supervisor_states()
    assert states == [{"entity_id": "light.test"}]
    assert any("/states" in c for c in calls)
    assert any("/api/states" in c for c in calls)


def test_bootstrap_habitus_zones_creates_multi_room_zones(monkeypatch):
    class DummyZone:
        def __init__(self, zone_id: str, name: str, room_ids: list[str]):
            self.zone_id = zone_id
            self.name = name
            self.room_ids = list(room_ids)
            self.entities = []
            self.settings = {}

    class DummyZoneEngine:
        def __init__(self) -> None:
            self.rooms: dict[str, dict] = {}
            self.zones: dict[str, DummyZone] = {}

        def register_room(self, room_id: str, name: str, entities: list[str]):
            self.rooms[room_id] = {"room_id": room_id, "name": name, "entities": list(entities)}

        def get_zone(self, zone_id: str):
            zone = self.zones.get(zone_id)
            if not zone:
                return None
            return {"zone_id": zone.zone_id, "name": zone.name, "rooms": zone.room_ids, "settings": zone.settings}

        def delete_zone(self, zone_id: str):
            self.zones.pop(zone_id, None)
            return True

        def create_zone(self, zone_id: str, name: str, room_ids: list[str], icon: str = "", priority: int = 0):
            zone = DummyZone(zone_id=zone_id, name=name, room_ids=room_ids)
            self.zones[zone_id] = zone
            return zone

        def set_zone_settings(self, zone_id: str, settings: dict):
            zone = self.zones.get(zone_id)
            if not zone:
                return False
            zone.settings.update(settings)
            return True

        def add_room_to_zone(self, zone_id: str, room_id: str):
            zone = self.zones.get(zone_id)
            if not zone:
                return False
            if room_id not in zone.room_ids:
                zone.room_ids.append(room_id)
            return True

    states = [
        {
            "entity_id": "light.wohnzimmer_decke",
            "attributes": {"friendly_name": "Wohnzimmer Decke", "area_id": "wohnzimmer"},
        },
        {
            "entity_id": "light.wohnflur_spots",
            "attributes": {"friendly_name": "Wohnflur Spots", "area_id": "wohnflur"},
        },
        {
            "entity_id": "binary_sensor.wohnzimmer_bewegung",
            "attributes": {"friendly_name": "Wohnzimmer Bewegung"},
        },
    ]

    engine = DummyZoneEngine()
    monkeypatch.setattr(hub_api, "_zone_engine", engine)
    monkeypatch.setattr(hub_api, "_fetch_supervisor_states", lambda: states)
    monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "false")

    app = Flask("hub_habitus_bootstrap_test")
    app.register_blueprint(hub_api.hub_bp)
    client = app.test_client()

    response = client.post("/api/v1/hub/habitus/management/bootstrap_zones", json={"overwrite": True})
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True

    wohn = next((z for z in payload["zones"] if z["zone_id"] == "zone:wohnbereich"), None)
    assert wohn is not None
    assert wohn["room_count"] >= 2
    assert "room:wohnzimmer" in wohn["room_ids"]
    assert "room:wohnflur" in wohn["room_ids"]
