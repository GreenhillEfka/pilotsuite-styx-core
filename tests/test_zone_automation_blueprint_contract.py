"""Query and payload contract coverage for zone-automation endpoints."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.api.v1 import zone_automation as zone_automation_module  # noqa: E402
from copilot_core.api.v1.zone_automation import zone_automation_bp  # noqa: E402


class _DummyConfig:
    def __init__(self, payload: dict[str, object]):
        self._payload = payload

    def to_dict(self):
        return dict(self._payload)


class _DummyController:
    def __init__(self):
        self._configs = {}
        self.last_habitus_sync_payload = None
        self.last_sync_payload = None
        self.last_override_payload = None
        self.last_presence_payload = None

    def get_zone_entities(self, zone_id: str):
        assert zone_id == "wohnung"
        return ["light.test", "switch.test"]

    def get_zone_entities_by_role(self, zone_id: str):
        assert zone_id == "wohnung"
        return {"lights": ["light.test"], "switches": ["switch.test"]}

    def get_zone_config(self, zone_id: str):
        self._configs[zone_id] = {"zone_id": zone_id}
        return self._configs[zone_id]

    def set_zone_config(self, zone_id: str, updates: dict[str, object]):
        assert zone_id == "wohnung"
        self.last_override_payload = updates
        return _DummyConfig(updates)

    def sync_habitus_zones(self, zones=None, clear_missing=False):
        payload = {"zones": zones, "clear_missing": clear_missing}
        self.last_habitus_sync_payload = payload
        self.last_sync_payload = payload
        return {
            "synced": len(zones or []),
            "created": 0,
            "deleted": 1 if clear_missing else 0,
            "habitus_zones": [],
            "ha_zones": [],
            "entity_zone_map": {},
        }

    def get_dashboard(self):
        return {"zones": []}

    def on_presence_detected(self, zone_id: str):
        self.last_presence_payload = (zone_id, True)
        return {"zone_id": zone_id, "detected": True}

    def on_presence_cleared(self, zone_id: str):
        self.last_presence_payload = (zone_id, False)
        return {"zone_id": zone_id, "detected": False}



def _client(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    controller = _DummyController()
    zone_automation_module.init_zone_automation_api(controller=controller, zone_engine=None)

    app = Flask(__name__)
    app.register_blueprint(zone_automation_bp)
    return app.test_client(), controller


def _auth() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


def test_list_zone_entities_by_role_true(monkeypatch):
    client, _ = _client(monkeypatch)

    response = client.get("/api/v1/zone-automation/zones/wohnung/entities?by_role=true", headers=_auth())
    assert response.status_code == 200
    payload = response.get_json()

    assert payload["ok"] is True
    assert payload["zone_id"] == "wohnung"
    assert payload["entities_by_role"]["lights"] == ["light.test"]


def test_list_zone_entities_by_role_01_alias(monkeypatch):
    client, _ = _client(monkeypatch)

    response = client.get("/api/v1/zone-automation/zones/wohnung/entities?by_role=1", headers=_auth())
    assert response.status_code == 200
    payload = response.get_json()

    assert payload["ok"] is True
    assert payload["entities_by_role"]["switches"] == ["switch.test"]


def test_list_zone_entities_default_behavior(monkeypatch):
    client, _ = _client(monkeypatch)

    response = client.get("/api/v1/zone-automation/zones/wohnung/entities", headers=_auth())
    assert response.status_code == 200
    payload = response.get_json()

    assert payload["ok"] is True
    assert payload["entities"] == ["light.test", "switch.test"]


def test_list_zone_entities_invalid_bool_query_rejected(monkeypatch):
    client, _ = _client(monkeypatch)

    response = client.get("/api/v1/zone-automation/zones/wohnung/entities?by_role=maybe", headers=_auth())
    assert response.status_code == 400
    payload = response.get_json()

    assert payload["ok"] is False
    assert payload["error"] == "invalid_query_param"
    assert "Invalid value for 'by_role'" in payload["message"]


def test_ensure_zones_habitus_sync_boolean_alias(monkeypatch):
    client, controller = _client(monkeypatch)

    response = client.post(
        "/api/v1/zone-automation/ensure-zones",
        headers=_auth(),
        json={"zone_ids": ["wohnzimmer"], "habitus_sync": "1"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["created"] == ["wohnzimmer"]
    assert controller.last_habitus_sync_payload["clear_missing"] is False


def test_ensure_zones_invalid_habitus_sync_rejected(monkeypatch):
    client, controller = _client(monkeypatch)

    response = client.post(
        "/api/v1/zone-automation/ensure-zones",
        headers=_auth(),
        json={"zone_ids": ["wohnzimmer"], "habitus_sync": "maybe"},
    )

    assert response.status_code == 400
    payload = response.get_json()

    assert payload["ok"] is False
    assert payload["error"] == "invalid_body_param"
    assert "Invalid value for 'habitus_sync'" in payload["message"]
    assert controller.last_habitus_sync_payload is None


def test_sync_invalid_clear_missing_rejected(monkeypatch):
    client, controller = _client(monkeypatch)

    response = client.post(
        "/api/v1/zone-automation/sync",
        headers=_auth(),
        json={"zones": [{"zone_id": "wohnzimmer"}], "clear_missing": "maybe"},
    )

    assert response.status_code == 400
    payload = response.get_json()

    assert payload["ok"] is False
    assert payload["error"] == "invalid_body_param"
    assert "Invalid value for 'clear_missing'" in payload["message"]
    assert controller.last_sync_payload is None


def test_sync_clear_missing_alias(monkeypatch):
    client, controller = _client(monkeypatch)

    response = client.post(
        "/api/v1/zone-automation/sync",
        headers=_auth(),
        json={"zones": [{"zone_id": "wohnzimmer"}], "clear_missing": "off"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["ok"] is True
    assert payload["synced"] == 1
    assert controller.last_sync_payload["clear_missing"] is False


def test_toggle_override_boolean_aliases(monkeypatch):
    client, controller = _client(monkeypatch)

    response = client.post(
        "/api/v1/zone-automation/zones/wohnung/override",
        headers=_auth(),
        json={"light_enabled": "1", "music_enabled": "off"},
    )

    assert response.status_code == 200
    payload = response.get_json()

    assert payload["ok"] is True
    assert payload["config"] == {"light": {"enabled": True}, "music": {"enabled": False}}
    assert controller.last_override_payload == {"light": {"enabled": True}, "music": {"enabled": False}}


def test_toggle_override_invalid_payload_rejected(monkeypatch):
    client, _ = _client(monkeypatch)

    response = client.post(
        "/api/v1/zone-automation/zones/wohnung/override",
        headers=_auth(),
        json={"light_enabled": "maybe"},
    )

    assert response.status_code == 400
    payload = response.get_json()

    assert payload["ok"] is False
    assert payload["error"] == "invalid_body_param"
    assert "Invalid value for 'light_enabled'" in payload["message"]


def test_presence_invalid_payload_rejected(monkeypatch):
    client, controller = _client(monkeypatch)

    response = client.post(
        "/api/v1/zone-automation/zones/wohnung/presence",
        headers=_auth(),
        json={"detected": "maybe"},
    )

    assert response.status_code == 400
    payload = response.get_json()

    assert payload["ok"] is False
    assert payload["error"] == "invalid_body_param"
    assert "Invalid value for 'detected'" in payload["message"]
    assert controller.last_presence_payload is None


def test_presence_alias_to_false(monkeypatch):
    client, controller = _client(monkeypatch)

    response = client.post(
        "/api/v1/zone-automation/zones/wohnung/presence",
        headers=_auth(),
        json={"detected": "0"},
    )

    assert response.status_code == 200
    payload = response.get_json()

    assert payload["ok"] is True
    assert payload["actions"] == {"zone_id": "wohnung", "detected": False}
    assert controller.last_presence_payload == ("wohnung", False)
