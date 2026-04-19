"""Contract tests for the F8.5 MQTT status API surface."""
from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path

from flask import Blueprint

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"


def _stub_shared_app_dependencies() -> None:
    mcp_stub = types.ModuleType("copilot_core.api.v1.mcp")
    mcp_stub.bp = Blueprint("mcp_stub", __name__, url_prefix="/api/v1/mcp")
    sys.modules["copilot_core.api.v1.mcp"] = mcp_stub

    tags_stub = types.ModuleType("copilot_core.tags")
    tags_stub.TagRegistry = type("TagRegistry", (), {})
    tags_stub.create_tag_service = lambda *a, **k: None
    sys.modules["copilot_core.tags"] = tags_stub

    tags_api_stub = types.ModuleType("copilot_core.tags.api")
    tags_api_stub.init_tags_api = lambda *a, **k: None
    sys.modules["copilot_core.tags.api"] = tags_api_stub


def _fresh_client(monkeypatch, *, auth_required: bool):
    for module_name in list(sys.modules):
        if module_name == "main" or module_name.startswith("copilot_core"):
            sys.modules.pop(module_name, None)

    addon_app_str = str(ADDON_APP)
    if addon_app_str in sys.path:
        sys.path.remove(addon_app_str)
    sys.path.insert(0, addon_app_str)

    monkeypatch.setenv("COPILOT_AUTH_REQUIRED", "true" if auth_required else "false")
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")

    _stub_shared_app_dependencies()

    main = importlib.import_module("main")
    app = main.create_app(options={})
    mqtt_module = importlib.import_module("copilot_core.mqtt_client")
    mqtt_module._mqtt_client = None
    return app.test_client()


class TestMqttApiContract:
    def test_requires_token_when_auth_is_enabled(self, monkeypatch):
        client = _fresh_client(monkeypatch, auth_required=True)

        response = client.get("/api/v1/mqtt/status")

        assert response.status_code == 401, response.get_data(as_text=True)
        assert response.get_json() == {
            "ok": False,
            "error": "Authentication required",
            "message": "Valid X-Auth-Token header or Bearer token required",
        }

    def test_returns_bounded_status_summary_shape(self, monkeypatch):
        client = _fresh_client(monkeypatch, auth_required=False)

        response = client.get("/api/v1/mqtt/status")

        assert response.status_code == 200, response.get_data(as_text=True)
        payload = response.get_json()
        assert payload["ok"] is True
        assert payload["version"] == 1

        status = payload["status"]
        assert isinstance(status["mqtt_available"], bool)
        assert isinstance(status["connected"], bool)
        assert status["broker_host"] == "172.30.33.1"
        assert status["broker_port"] == 1883
        assert status["topic_prefix"] == "pilotsuite/"
        assert isinstance(status["active_subscriptions"], int)
        assert status["active_subscriptions"] >= 0
