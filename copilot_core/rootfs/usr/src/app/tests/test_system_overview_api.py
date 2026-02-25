"""Tests for /api/v1/system overview endpoints."""

from __future__ import annotations

import time
from types import SimpleNamespace

from flask import Flask

from copilot_core.api.v1 import system_status
from copilot_core.hub import api as hub_api


class _FakeZoneEngine:
    def get_overview(self):
        return SimpleNamespace(
            zones=[
                {
                    "zone_id": "zone:wohnbereich",
                    "name": "Wohnbereich",
                    "enabled": True,
                }
            ]
        )

    def get_zone(self, zone_id: str):
        if zone_id != "zone:wohnbereich":
            return {}
        return {
            "zone_id": zone_id,
            "name": "Wohnbereich",
            "entities": [
                "sensor.ai_home_copilot_comfort",
                "binary_sensor.ai_home_copilot_motion",
                "sensor.temperature_wohnzimmer",
                "sensor.humidity_wohnzimmer",
            ],
            "settings": {},
        }


def _build_app() -> Flask:
    app = Flask("system_overview_test")
    app.config["COPILOT_SERVICES"] = {}
    app.config["STARTUP_TIME"] = time.time() - 30
    app.register_blueprint(system_status.system_status_bp)
    return app


def test_system_overview_endpoint(monkeypatch):
    monkeypatch.setattr(
        hub_api,
        "_fetch_supervisor_states",
        lambda: [
            {
                "entity_id": "sensor.ai_home_copilot_comfort",
                "state": "0.76",
                "attributes": {"friendly_name": "PilotSuite Comfort"},
            },
            {
                "entity_id": "binary_sensor.ai_home_copilot_motion",
                "state": "on",
                "attributes": {"friendly_name": "PilotSuite Motion"},
            },
            {
                "entity_id": "sensor.temperature_wohnzimmer",
                "state": "22.4",
                "attributes": {"friendly_name": "Temperatur Wohnzimmer"},
            },
            {
                "entity_id": "sensor.humidity_wohnzimmer",
                "state": "44.3",
                "attributes": {"friendly_name": "Luftfeuchte Wohnzimmer"},
            },
        ],
    )
    monkeypatch.setattr(hub_api, "_zone_engine", _FakeZoneEngine())
    system_status._OVERVIEW_CACHE["timestamp"] = 0.0
    system_status._OVERVIEW_CACHE["payload"] = None

    app = _build_app()
    client = app.test_client()
    response = client.get("/api/v1/system/overview?force=true&sensor_limit=120")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert "overall" in payload
    assert payload["sensors"]["sensor_count"] >= 2
    assert payload["zones"][0]["zone_id"] == "zone:wohnbereich"


def test_system_sensors_endpoint(monkeypatch):
    monkeypatch.setattr(
        hub_api,
        "_fetch_supervisor_states",
        lambda: [
            {
                "entity_id": "sensor.ai_home_copilot_mood",
                "state": "happy",
                "attributes": {"friendly_name": "PilotSuite Mood"},
            },
            {
                "entity_id": "sensor.ai_home_copilot_energy",
                "state": "123.4",
                "attributes": {"friendly_name": "PilotSuite Energy"},
            },
        ],
    )
    monkeypatch.setattr(hub_api, "_zone_engine", None)
    system_status._OVERVIEW_CACHE["timestamp"] = 0.0
    system_status._OVERVIEW_CACHE["payload"] = None

    app = _build_app()
    client = app.test_client()
    response = client.get("/api/v1/system/sensors?force=true&limit=80")
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["summary"]["total_entities"] >= 2
    assert isinstance(payload["items"], list)


def test_system_cache_clear(monkeypatch):
    monkeypatch.setattr(hub_api, "_fetch_supervisor_states", lambda: [])
    monkeypatch.setattr(hub_api, "_zone_engine", None)
    app = _build_app()
    client = app.test_client()

    # Prime cache
    r1 = client.get("/api/v1/system/overview")
    assert r1.status_code == 200
    assert system_status._OVERVIEW_CACHE["payload"] is not None

    # Clear cache
    r2 = client.post("/api/v1/system/cache/clear")
    assert r2.status_code == 200
    body = r2.get_json()
    assert body["ok"] is True
    assert system_status._OVERVIEW_CACHE["payload"] is None
