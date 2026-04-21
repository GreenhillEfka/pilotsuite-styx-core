"""Contract tests for the CORE-HABITUS-202-A /api/v1/habitus/zones seam."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest
from flask import Flask

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))

EXPECTED_MODULE_IDS = {
    "light",
    "motion",
    "music",
    "volume",
    "tv",
    "climate",
    "camera",
}
EXPECTED_METRICS = {
    "entity_count": 3,
    "active_lights": 1,
    "avg_temperature": 21.5,
    "avg_humidity": 48.0,
    "occupancy": True,
    "last_activity": None,
    "energy_consumption_kwh": 0.4,
}


@pytest.fixture
def habitus_api_module():
    sys.modules.pop("copilot_core.api.v1.habitus_zones", None)
    return importlib.import_module("copilot_core.api.v1.habitus_zones")


@pytest.fixture
def client(habitus_api_module, monkeypatch):
    monkeypatch.setattr(habitus_api_module, "_get_zone_metrics", lambda zone_type: dict(EXPECTED_METRICS))

    app = Flask(__name__)
    app.register_blueprint(habitus_api_module.bp)
    return app.test_client(), habitus_api_module


def test_get_habitus_zones_requires_auth_front_door(client, monkeypatch):
    test_client, habitus_api_module = client
    monkeypatch.setattr(habitus_api_module, "validate_token", lambda request: False)

    response = test_client.get("/api/v1/habitus/zones")

    assert response.status_code == 401, response.get_data(as_text=True)
    assert response.get_json() == {
        "error": "unauthorized",
        "message": "Valid X-Auth-Token or Bearer token required",
    }


def test_get_habitus_zones_returns_default_metrics_and_canonical_module_overrides(client, monkeypatch):
    test_client, habitus_api_module = client
    monkeypatch.setattr(habitus_api_module, "validate_token", lambda request: True)

    response = test_client.get("/api/v1/habitus/zones")

    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["total_zones"] == 10
    assert len(payload["zones"]) == 10

    for zone in payload["zones"]:
        assert set(zone["module_overrides"].keys()) == EXPECTED_MODULE_IDS
        assert zone["metrics"] == EXPECTED_METRICS


def test_get_habitus_zones_can_omit_metrics_without_changing_zone_count(client, monkeypatch):
    test_client, habitus_api_module = client
    monkeypatch.setattr(habitus_api_module, "validate_token", lambda request: True)

    response = test_client.get("/api/v1/habitus/zones?include_metrics=false")

    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["status"] == "ok"
    assert payload["total_zones"] == 10
    assert len(payload["zones"]) == 10
    assert all("metrics" not in zone for zone in payload["zones"])
    assert all(set(zone["module_overrides"].keys()) == EXPECTED_MODULE_IDS for zone in payload["zones"])


def test_get_habitus_zones_rejects_invalid_zone_type_with_existing_400_path(client, monkeypatch):
    test_client, habitus_api_module = client
    monkeypatch.setattr(habitus_api_module, "validate_token", lambda request: True)

    response = test_client.get("/api/v1/habitus/zones?zone_type=garage")

    assert response.status_code == 400, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["error"] == "invalid_zone_type"
    assert "Invalid zone type: garage." in payload["message"]
