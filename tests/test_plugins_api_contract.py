"""Contract tests for the F7.1 plugin SDK API surface."""
from __future__ import annotations

import importlib
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock

mock_security = MagicMock()
mock_security.require_token = lambda f: f
sys.modules["copilot_core.api.security"] = mock_security

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))

from flask import Blueprint


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


def _fresh_client():
    _stub_shared_app_dependencies()
    for module_name in (
        "main",
        "copilot_core.api.v1.plugins",
        "copilot_core.hub.plugin_manager",
    ):
        sys.modules.pop(module_name, None)

    main = importlib.import_module("main")
    app = main.create_app(options={})

    plugins_module = importlib.import_module("copilot_core.api.v1.plugins")
    plugins_module._plugin_manager = None
    return app.test_client(), plugins_module


class TestPluginsApiContract:
    def test_lists_registered_plugins_with_bounded_summary_shape(self):
        client, _plugins_module = _fresh_client()

        response = client.get("/api/v1/plugins")

        assert response.status_code == 200, response.get_data(as_text=True)
        payload = response.get_json()
        assert payload["ok"] is True
        assert payload["version"] == 1
        assert isinstance(payload["total"], int)
        assert payload["total"] >= 1
        assert isinstance(payload["plugins"], list)
        first = payload["plugins"][0]
        for field in (
            "plugin_id",
            "name",
            "version",
            "category",
            "status",
            "author",
            "description",
        ):
            assert field in first, f"missing field: {field}"

    def test_register_activate_and_deactivate_plugin_over_existing_registry(self):
        client, plugins_module = _fresh_client()

        register_response = client.post(
            "/api/v1/plugins/register",
            json={
                "plugin_id": "grid_guard",
                "name": "Grid Guard",
                "version": "1.0.0",
                "author": "PilotSuite",
                "category": "energy",
                "requires": ["energy_management"],
            },
        )
        assert register_response.status_code == 201, register_response.get_data(as_text=True)
        assert register_response.get_json() == {"ok": True, "plugin_id": "grid_guard"}

        activate_response = client.post("/api/v1/plugins/grid_guard/activate")
        assert activate_response.status_code == 200, activate_response.get_data(as_text=True)
        assert activate_response.get_json() == {"ok": True, "plugin_id": "grid_guard"}

        detail_response = client.get("/api/v1/plugins/grid_guard")
        assert detail_response.status_code == 200, detail_response.get_data(as_text=True)
        assert detail_response.get_json()["plugin"]["status"] == "active"

        deactivate_response = client.post("/api/v1/plugins/grid_guard/deactivate")
        assert deactivate_response.status_code == 200, deactivate_response.get_data(as_text=True)
        assert deactivate_response.get_json() == {"ok": True, "plugin_id": "grid_guard"}

        plugins_module._plugin_manager = None
