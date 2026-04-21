"""Contract tests for the CORE-HABITUS-202-D zone presence hold seam."""
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


@pytest.fixture
def security_module():
    return importlib.import_module("copilot_core.api.security")


@pytest.fixture
def presence_api_module():
    sys.modules.pop("copilot_core.api.v1.presence", None)
    return importlib.import_module("copilot_core.api.v1.presence")


@pytest.fixture
def client(presence_api_module):
    presence_api_module._ZONE_HOLD_MAP.clear()

    app = Flask(__name__)
    app.register_blueprint(presence_api_module.presence_bp)
    return app.test_client(), presence_api_module


def test_zone_presence_hold_requires_auth_front_door(client, security_module, monkeypatch):
    test_client, _presence_api_module = client
    monkeypatch.setattr(security_module, "validate_token", lambda request: False)

    response = test_client.post(
        "/api/v1/presence/zone/presence/living/hold",
        json={"hold": "force_on"},
    )

    assert response.status_code == 401, response.get_data(as_text=True)
    assert response.get_json() == {
        "ok": False,
        "error": "Authentication required",
        "message": "Valid X-Auth-Token header or Bearer token required",
    }


@pytest.mark.parametrize(
    ("route_zone_id", "stored_zone_id", "hold"),
    [
        ("living", "zone:living", "auto"),
        ("living", "zone:living", "force_on"),
        ("zone:kitchen", "zone:kitchen", "force_off"),
    ],
)
def test_zone_presence_hold_accepts_only_valid_states_and_stores_canonical_zone_id(
    client,
    security_module,
    monkeypatch,
    route_zone_id,
    stored_zone_id,
    hold,
):
    test_client, presence_api_module = client
    monkeypatch.setattr(security_module, "validate_token", lambda request: True)

    response = test_client.post(
        f"/api/v1/presence/zone/presence/{route_zone_id}/hold",
        json={"hold": hold},
    )

    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json() == {
        "ok": True,
        "zone_id": stored_zone_id,
        "hold": hold,
    }
    assert presence_api_module.get_zone_hold_state(stored_zone_id) == hold


def test_zone_presence_hold_rejects_invalid_states(client, security_module, monkeypatch):
    test_client, presence_api_module = client
    monkeypatch.setattr(security_module, "validate_token", lambda request: True)

    response = test_client.post(
        "/api/v1/presence/zone/presence/bedroom/hold",
        json={"hold": "manual_override"},
    )

    assert response.status_code == 400, response.get_data(as_text=True)
    assert response.get_json()["ok"] is False
    assert response.get_json()["error"].startswith("Invalid hold state: manual_override.")
    assert presence_api_module.get_zone_hold_state("zone:bedroom") == "auto"
