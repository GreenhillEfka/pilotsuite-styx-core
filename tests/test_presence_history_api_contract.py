"""Contract tests for the CORE-HABITUS-202-F presence history seam."""
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


def test_presence_history_requires_auth_front_door(client, security_module, monkeypatch):
    test_client, _presence_api_module = client
    monkeypatch.setattr(security_module, "validate_token", lambda request: False)

    response = test_client.get("/api/v1/presence/history")

    assert response.status_code == 401, response.get_data(as_text=True)
    assert response.get_json() == {
        "ok": False,
        "error": "Authentication required",
        "message": "Valid X-Auth-Token header or Bearer token required",
    }


def test_presence_history_returns_default_newest_first_payload(client, security_module, monkeypatch):
    test_client, presence_api_module = client
    monkeypatch.setattr(security_module, "validate_token", lambda request: True)

    older_event = {
        "person_id": "person.alice",
        "person_name": "Alice",
        "event_type": "arrived",
        "from_state": "not_home",
        "to_state": "home",
        "trigger_source": "ble",
        "zone": "living_room",
        "timestamp": 1700000000.0,
    }
    newer_event = {
        "person_id": "person.bob",
        "person_name": "Bob",
        "event_type": "departed",
        "from_state": "home",
        "to_state": "not_home",
        "trigger_source": "ha",
        "zone": "entry",
        "timestamp": 1700000100.0,
    }
    presence_api_module._presence_history.appendleft(older_event)
    presence_api_module._presence_history.appendleft(newer_event)

    response = test_client.get("/api/v1/presence/history")

    assert response.status_code == 200, response.get_data(as_text=True)
    assert response.get_json() == {
        "ok": True,
        "events": [newer_event, older_event],
    }


def test_presence_history_clamps_limit_to_bounded_maximum(client, security_module, monkeypatch):
    test_client, presence_api_module = client
    monkeypatch.setattr(security_module, "validate_token", lambda request: True)

    for index in range(205):
        presence_api_module._presence_history.appendleft({
            "person_id": f"person.{index}",
            "person_name": f"Person {index}",
            "event_type": "arrived",
            "from_state": "not_home",
            "to_state": "home",
            "trigger_source": "ha",
            "zone": f"zone-{index}",
            "timestamp": 1700000000.0 + index,
        })

    response = test_client.get("/api/v1/presence/history?limit=999")

    assert response.status_code == 200, response.get_data(as_text=True)
    payload = response.get_json()
    assert payload["ok"] is True
    assert len(payload["events"]) == 200
    assert payload["events"][0]["person_id"] == "person.204"
    assert payload["events"][-1]["person_id"] == "person.5"
