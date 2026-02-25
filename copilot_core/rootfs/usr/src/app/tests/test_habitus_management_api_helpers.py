from __future__ import annotations

import os

from copilot_core.hub import api as hub_api


def test_build_habitus_recommendations_marks_camera_and_standard_metrics():
    states = [
        {
            "entity_id": "camera.wohnzimmer_cam",
            "attributes": {"friendly_name": "Wohnzimmer Cam"},
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
