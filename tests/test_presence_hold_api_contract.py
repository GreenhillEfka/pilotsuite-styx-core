"""Contract tests for the CORE-HABITUS-202-G presence hold seam."""
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


def test_presence_hold_requires_auth_front_door(client, security_module, monkeypatch):
    test_client, _presence_api_module = client
    monkeypatch.setattr(security_module, "validate_token", lambda request: False)

    response = test_client.post("/api/v1/presence/hold", json={"person_id": "person.alice"})

    assert response.status_code == 401, response.get_data(as_text=True)
    assert response.get_json() == {
        "ok": False,
        "error": "Authentication required",
        "message": "Valid X-Auth-Token header or Bearer token required",
    }


def test_presence_hold_requires_person_id(client, security_module, monkeypatch):
    test_client, _presence_api_module = client
    monkeypatch.setattr(security_module, "validate_token", lambda request: True)

    response = test_client.post("/api/v1/presence/hold", json={"state": "home"})

    assert response.status_code == 400, response.get_data(as_text=True)
    assert response.get_json() == {
        "ok": False,
        "error": "Missing person_id",
    }


def test_presence_hold_creates_person_with_canonical_hold_payload(client, security_module, monkeypatch):
    test_client, presence_api_module = client
    monkeypatch.setattr(security_module, "validate_token", lambda request: True)
    monkeypatch.setattr(presence_api_module.time, "time", lambda: 1700000000.0)

    response = test_client.post(
        "/api/v1/presence/hold",
        json={
            "person_id": "person.alice",
            "state": "home",
            "reason": "manual",
            "duration": 3600,
        },
    )

    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json() == {
        "ok": True,
        "hold_set": "home",
        "person_id": "person.alice",
        "reason": "manual",
        "hold_until": 1700003600.0,
    }
    assert presence_api_module._presence_map["person.alice"] == {
        "person_id": "person.alice",
        "name": "person.alice",
        "state": "home",
        "sources": {},
        "hold": "home",
        "hold_reason": "manual",
        "hold_until": 1700003600.0,
        "since": 1700000000.0,
        "updated_at": 1700000000.0,
    }


def test_presence_hold_updates_existing_person_with_canonical_hold_payload(client, security_module, monkeypatch):
    test_client, presence_api_module = client
    monkeypatch.setattr(security_module, "validate_token", lambda request: True)
    monkeypatch.setattr(presence_api_module.time, "time", lambda: 1700000200.0)

    presence_api_module._presence_map["person.alice"] = {
        "person_id": "person.alice",
        "name": "Alice",
        "state": "home",
        "sources": {
            "ha": {
                "state": "home",
                "zone": "living_room",
                "since": 1699999900.0,
                "updated_at": 1699999950.0,
                "timeout": 300,
            }
        },
        "hold": None,
        "hold_reason": None,
        "hold_until": None,
        "since": 1699999900.0,
        "updated_at": 1699999950.0,
    }

    response = test_client.post(
        "/api/v1/presence/hold",
        json={
            "person_id": "person.alice",
            "state": "away",
            "reason": "sleeping",
        },
    )

    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json() == {
        "ok": True,
        "hold_set": "not_home",
        "person_id": "person.alice",
        "reason": "sleeping",
        "hold_until": None,
    }
    assert presence_api_module._presence_map["person.alice"] == {
        "person_id": "person.alice",
        "name": "Alice",
        "state": "not_home",
        "sources": {
            "ha": {
                "state": "home",
                "zone": "living_room",
                "since": 1699999900.0,
                "updated_at": 1699999950.0,
                "timeout": 300,
            }
        },
        "hold": "not_home",
        "hold_reason": "sleeping",
        "hold_until": None,
        "since": 1699999900.0,
        "updated_at": 1700000200.0,
    }
    assert list(presence_api_module._presence_history) == [
        {
            "person_id": "person.alice",
            "person_name": "Alice",
            "event_type": "departed",
            "from_state": "home",
            "to_state": "not_home",
            "trigger_source": "hold",
            "reason": "sleeping",
            "timestamp": 1700000200.0,
        }
    ]
