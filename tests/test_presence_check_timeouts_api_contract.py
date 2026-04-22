"""Contract tests for the CORE-HABITUS-202-I presence-check-timeouts seam."""
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


def test_presence_check_timeouts_requires_auth_front_door(client, security_module, monkeypatch):
    test_client, _presence_api_module = client
    monkeypatch.setattr(security_module, "validate_token", lambda request: False)

    response = test_client.post("/api/v1/presence/check_timeouts")

    assert response.status_code == 401, response.get_data(as_text=True)
    assert response.get_json() == {
        "ok": False,
        "error": "Authentication required",
        "message": "Valid X-Auth-Token header or Bearer token required",
    }


def test_presence_check_timeouts_returns_canonical_noop_payload(client, security_module, monkeypatch):
    test_client, presence_api_module = client
    monkeypatch.setattr(security_module, "validate_token", lambda request: True)
    monkeypatch.setattr(presence_api_module.time, "time", lambda: 1700000400.0)

    presence_api_module._presence_map["person.alice"] = {
        "person_id": "person.alice",
        "name": "Alice",
        "state": "home",
        "sources": {
            "ha": {
                "state": "home",
                "zone": "living_room",
                "since": 1700000000.0,
                "updated_at": 1700000305.0,
                "timeout": 300,
            }
        },
        "since": 1700000000.0,
        "updated_at": 1700000305.0,
    }

    response = test_client.post("/api/v1/presence/check_timeouts")

    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json() == {
        "ok": True,
        "timed_out": [],
        "state_changed": False,
    }
    assert presence_api_module._presence_map["person.alice"]["state"] == "home"
    assert presence_api_module._presence_map["person.alice"]["sources"]["ha"]["state"] == "home"
    assert list(presence_api_module._presence_history) == []


def test_presence_check_timeouts_recomputes_timeout_driven_state_change(client, security_module, monkeypatch):
    test_client, presence_api_module = client
    monkeypatch.setattr(security_module, "validate_token", lambda request: True)
    monkeypatch.setattr(presence_api_module.time, "time", lambda: 1700000601.0)

    presence_api_module._presence_map["person.alice"] = {
        "person_id": "person.alice",
        "name": "Alice",
        "state": "home",
        "sources": {
            "ha": {
                "state": "home",
                "zone": "living_room",
                "since": 1700000000.0,
                "updated_at": 1700000000.0,
                "timeout": 300,
            },
            "ble": {
                "state": "not_home",
                "zone": "entry",
                "since": 1700000000.0,
                "updated_at": 1700000500.0,
                "timeout": 300,
            },
        },
        "since": 1700000000.0,
        "updated_at": 1700000000.0,
    }

    response = test_client.post("/api/v1/presence/check_timeouts")

    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json() == {
        "ok": True,
        "timed_out": ["person.alice"],
        "state_changed": True,
    }
    assert presence_api_module._presence_map["person.alice"]["state"] == "not_home"
    assert presence_api_module._presence_map["person.alice"]["sources"]["ha"]["state"] == "not_home"
    assert presence_api_module._presence_map["person.alice"]["sources"]["ble"]["state"] == "not_home"
    assert list(presence_api_module._presence_history) == [
        {
            "person_id": "person.alice",
            "person_name": "Alice",
            "event_type": "departed",
            "from_state": "home",
            "to_state": "not_home",
            "trigger_source": "timeout",
            "timestamp": 1700000601.0,
        }
    ]
