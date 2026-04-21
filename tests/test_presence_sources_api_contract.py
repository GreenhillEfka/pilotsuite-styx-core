"""Contract tests for the CORE-HABITUS-202-E presence sources seam."""
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
    presence_api_module.clear_presence_data()

    app = Flask(__name__)
    app.register_blueprint(presence_api_module.presence_bp)
    return app.test_client(), presence_api_module


def test_presence_sources_requires_auth_front_door(client, security_module, monkeypatch):
    test_client, _presence_api_module = client
    monkeypatch.setattr(security_module, "validate_token", lambda request: False)

    response = test_client.get("/api/v1/presence/sources?person_id=person.alice")

    assert response.status_code == 401, response.get_data(as_text=True)
    assert response.get_json() == {
        "ok": False,
        "error": "Authentication required",
        "message": "Valid X-Auth-Token header or Bearer token required",
    }


def test_presence_sources_requires_person_id(client, security_module, monkeypatch):
    test_client, _presence_api_module = client
    monkeypatch.setattr(security_module, "validate_token", lambda request: True)

    response = test_client.get("/api/v1/presence/sources")

    assert response.status_code == 400, response.get_data(as_text=True)
    assert response.get_json() == {
        "ok": False,
        "error": "Missing person_id",
    }


def test_presence_sources_rejects_unknown_person(client, security_module, monkeypatch):
    test_client, _presence_api_module = client
    monkeypatch.setattr(security_module, "validate_token", lambda request: True)

    response = test_client.get("/api/v1/presence/sources?person_id=person.unknown")

    assert response.status_code == 404, response.get_data(as_text=True)
    assert response.get_json() == {
        "ok": False,
        "error": "Person not found",
    }


def test_presence_sources_returns_canonical_seeded_person_payload(client, security_module, monkeypatch):
    test_client, presence_api_module = client
    monkeypatch.setattr(security_module, "validate_token", lambda request: True)

    presence_api_module._presence_map["person.alice"] = {
        "person_id": "person.alice",
        "name": "Alice",
        "state": "home",
        "sources": {
            "ha": {
                "state": "home",
                "zone": "living_room",
                "since": 1700000000.0,
                "updated_at": 1700000001.0,
                "timeout": 300,
            },
            "ble": {
                "state": "home",
                "zone": "entry",
                "since": 1700000002.0,
                "updated_at": 1700000003.0,
                "timeout": 120,
            },
        },
        "hold": "home",
        "hold_reason": "manual",
        "since": 1700000000.0,
        "updated_at": 1700000003.0,
    }

    response = test_client.get("/api/v1/presence/sources?person_id=person.alice")

    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json() == {
        "ok": True,
        "person_id": "person.alice",
        "name": "Alice",
        "sources": {
            "ha": {
                "state": "home",
                "zone": "living_room",
                "since": 1700000000.0,
                "updated_at": 1700000001.0,
                "timeout": 300,
            },
            "ble": {
                "state": "home",
                "zone": "entry",
                "since": 1700000002.0,
                "updated_at": 1700000003.0,
                "timeout": 120,
            },
        },
        "hold": "home",
        "hold_reason": "manual",
        "aggregated_state": "home",
    }
