"""Contract tests for the CORE-HABITUS-202-C zone presence state seam."""
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
    if hasattr(presence_api_module.presence_bp, "_zone_presence_state"):
        delattr(presence_api_module.presence_bp, "_zone_presence_state")

    app = Flask(__name__)
    app.register_blueprint(presence_api_module.presence_bp)
    return app.test_client(), presence_api_module


def test_zone_presence_state_requires_auth_front_door(client, security_module, monkeypatch):
    test_client, _presence_api_module = client
    monkeypatch.setattr(security_module, "validate_token", lambda request: False)

    response = test_client.post(
        "/api/v1/presence/zone/presence/living/state",
        json={"occupied": True},
    )

    assert response.status_code == 401, response.get_data(as_text=True)
    assert response.get_json() == {
        "ok": False,
        "error": "Authentication required",
        "message": "Valid X-Auth-Token header or Bearer token required",
    }


def test_zone_presence_state_normalizes_zone_id_and_stores_payload(client, security_module, monkeypatch):
    test_client, presence_api_module = client
    monkeypatch.setattr(security_module, "validate_token", lambda request: True)
    monkeypatch.setattr(presence_api_module.time, "time", lambda: 1713700800.0)

    response = test_client.post(
        "/api/v1/presence/zone/presence/living/state",
        json={
            "occupied": True,
            "primary_source": "person.andreas",
            "confidence": 0.95,
            "hold_state": "force_on",
        },
    )

    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json() == {
        "ok": True,
        "zone_id": "zone:living",
        "occupied": True,
        "stored": True,
    }
    assert presence_api_module.get_zone_presence_state("zone:living") == {
        "occupied": True,
        "primary_source": "person.andreas",
        "confidence": 0.95,
        "hold_state": "force_on",
        "updated_at": 1713700800.0,
    }


def test_zone_presence_state_keeps_prefixed_zone_id_and_defaults_optional_fields(client, security_module, monkeypatch):
    test_client, presence_api_module = client
    monkeypatch.setattr(security_module, "validate_token", lambda request: True)
    monkeypatch.setattr(presence_api_module.time, "time", lambda: 1713700900.0)

    response = test_client.post(
        "/api/v1/presence/zone/presence/zone:kitchen/state",
        json={},
    )

    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json() == {
        "ok": True,
        "zone_id": "zone:kitchen",
        "occupied": False,
        "stored": True,
    }
    assert presence_api_module.get_zone_presence_state("zone:kitchen") == {
        "occupied": False,
        "primary_source": None,
        "confidence": 0.0,
        "hold_state": "auto",
        "updated_at": 1713700900.0,
    }
