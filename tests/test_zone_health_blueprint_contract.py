"""Regression coverage for zone health blueprint optional-dependency behavior."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.api.v1 import zone_health as zone_health_module  # noqa: E402
from copilot_core.api.v1.zone_health import init_zone_health_api, zone_health_bp  # noqa: E402


def _client(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("SUPERVISOR_TOKEN", "test-supervisor-token")
    monkeypatch.setattr(zone_health_module, "http_requests", None)
    monkeypatch.setattr(zone_health_module, "_checker", None)
    init_zone_health_api(zone_automation=None, module_registry=None)

    app = Flask(__name__)
    app.register_blueprint(zone_health_bp)
    return app.test_client()


def test_zone_health_blueprint_degrades_cleanly_without_requests(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    response = client.get("/api/v1/zone/health", headers=headers)
    assert response.status_code == 503
    assert response.get_json()["error"] == "zone_health_unavailable"

    detail_response = client.get("/api/v1/zone/health/wohnzimmer", headers=headers)
    assert detail_response.status_code == 503
    assert detail_response.get_json()["error"] == "zone_health_unavailable"


class _Overview:
    def __init__(self, zones):
        self.zones = zones


class _ZoneAutomationStub:
    def get_overview(self):
        return _Overview([
            {
                "zone_id": "zone:living",
                "name_de": "Wohnzimmer",
                "zone_type": "living",
                "entities": {"sensors": [
                    "sensor.living_temp",
                    "sensor.living_humidity",
                    "sensor.living_co2",
                    "sensor.living_lux",
                ]},
                "entities_by_role": {
                    "sensors": [
                        "sensor.living_temp",
                        "sensor.living_humidity",
                        "sensor.living_co2",
                        "sensor.living_lux",
                    ]
                },
            }
        ])

    def get_zone(self, zone_id):
        return {
            "zone_id": zone_id,
            "name_de": "Wohnzimmer",
            "zone_type": "living",
            "enabled_modules": [],
        }

    def get_all_states(self):
        return [
            {
                "zone_id": "zone:living",
                "name": "Wohnzimmer",
                "zone_type": "living",
                "enabled_modules": [],
            }
        ]

    def get_zone_entities_by_role(self, _zone_id):
        return {
            "sensors": [
                "sensor.living_temp",
                "sensor.living_humidity",
                "sensor.living_co2",
                "sensor.living_lux",
            ]
        }

    def get_automation_mode(self, _zone_id):
        return "auto"


class _PresenceManagerStub:
    def __init__(self, now):
        self._now = now

    def get_zone_presence(self, _zone_id):
        return {
            "confidence": 0.93,
            "presence": True,
            "last_seen": self._now.isoformat(),
        }


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload
        self.ok = True

    def json(self):
        return self._payload


class _FakeRequests:
    def __init__(self, payload):
        self._payload = payload

    def get(self, *_args, **_kwargs):
        return _FakeResponse(self._payload)


def _client_with_services(monkeypatch, *, zone_automation=None, zone_presence_manager=None, states=None):
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("SUPERVISOR_TOKEN", "test-supervisor-token")
    monkeypatch.setattr(zone_health_module, "http_requests", None)
    monkeypatch.setattr(zone_health_module, "_checker", None)

    if states is not None:
        monkeypatch.setattr(zone_health_module, "http_requests", _FakeRequests(states))

    init_zone_health_api(
        zone_automation=zone_automation,
        module_registry=None,
        zone_presence_manager=zone_presence_manager,
    )

    app = Flask(__name__)
    app.register_blueprint(zone_health_bp)
    return app.test_client()


def test_zone_health_correlations_endpoints_return_payload(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    states = [
        {"entity_id": "sensor.living_temp", "state": "22.0", "attributes": {"unit_of_measurement": "°C"}, "last_updated": now.isoformat(), "last_changed": now.isoformat()},
        {"entity_id": "sensor.living_humidity", "state": "48", "attributes": {"unit_of_measurement": "%"}, "last_updated": now.isoformat(), "last_changed": now.isoformat()},
        {"entity_id": "sensor.living_co2", "state": "680", "attributes": {"unit_of_measurement": "ppm"}, "last_updated": now.isoformat(), "last_changed": now.isoformat()},
        {"entity_id": "sensor.living_lux", "state": "120", "attributes": {"unit_of_measurement": "lx"}, "last_updated": now.isoformat(), "last_changed": now.isoformat()},
    ]

    client = _client_with_services(
        monkeypatch,
        zone_automation=_ZoneAutomationStub(),
        zone_presence_manager=_PresenceManagerStub(now),
        states=states,
    )

    headers = {"Authorization": "Bearer test-token"}

    response = client.get("/api/v1/zone/health/correlations", headers=headers)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert "wohnzimmer" in str(payload["correlations"]).lower()
    assert payload["summary"]["total_zones"] >= 1

    insight_response = client.get("/api/v1/zone/health/correlations/insights", headers=headers)
    assert insight_response.status_code == 200
    insight_payload = insight_response.get_json()
    assert insight_payload["ok"] is True


def test_zone_health_single_zone_correlation_returns_payload(monkeypatch) -> None:
    now = datetime.now(timezone.utc)
    states = [
        {"entity_id": "sensor.living_temp", "state": "22.0", "attributes": {"unit_of_measurement": "°C"}, "last_updated": now.isoformat(), "last_changed": now.isoformat()},
        {"entity_id": "sensor.living_humidity", "state": "45", "attributes": {"unit_of_measurement": "%"}, "last_updated": now.isoformat(), "last_changed": now.isoformat()},
        {"entity_id": "sensor.living_co2", "state": "780", "attributes": {"unit_of_measurement": "ppm"}, "last_updated": now.isoformat(), "last_changed": now.isoformat()},
        {"entity_id": "sensor.living_lux", "state": "190", "attributes": {"unit_of_measurement": "lx"}, "last_updated": now.isoformat(), "last_changed": now.isoformat()},
    ]

    client = _client_with_services(
        monkeypatch,
        zone_automation=_ZoneAutomationStub(),
        zone_presence_manager=_PresenceManagerStub(now),
        states=states,
    )

    headers = {"Authorization": "Bearer test-token"}
    response = client.get("/api/v1/zone/health/zone:living/correlation", headers=headers)
    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["zone_id"] == "zone:living"
    assert payload["correlation"]["is_occupied"] is True
    assert payload["correlation"]["health_score"] >= 0

