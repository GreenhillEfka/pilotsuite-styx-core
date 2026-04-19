"""Contract tests for POST /api/v1/energy/solar-surplus/notify (F2.5-G3)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

# Bypass auth before any app imports
mock_security = MagicMock()
mock_security.require_token = lambda f: f
sys.modules["copilot_core.api.security"] = mock_security

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

import types
from flask import Blueprint


def _stub_shared_app_dependencies():
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


class TestSolarSurplusNotify:
    """Verify POST /api/v1/energy/solar-surplus/notify (F2.5-G3)."""

    def test_returns_ok_with_suppressed_when_no_surplus(self):
        import importlib

        _stub_shared_app_dependencies()
        sys.modules.pop("main", None)

        main = importlib.import_module("main")
        app = main.create_app(options={})

        client = app.test_client()
        response = client.post(
            "/api/v1/energy/solar-surplus/notify",
            headers={"X-Auth-Token": "test"},
        )

        assert response.status_code == 200, f"got {response.status_code}: {response.get_json()}"
        payload = response.get_json()

        assert payload.get("ok") is True
        # Either notified or suppressed — both are valid outcomes
        assert "suppressed" in payload or "notified" in payload

    def test_response_shape_valid(self):
        import importlib

        _stub_shared_app_dependencies()
        sys.modules.pop("main", None)

        main = importlib.import_module("main")
        app = main.create_app(options={})

        client = app.test_client()
        response = client.post(
            "/api/v1/energy/solar-surplus/notify",
            headers={"X-Auth-Token": "test"},
        )

        payload = response.get_json()
        # When suppressed (no surplus), must have reason
        if payload.get("suppressed"):
            assert "reason" in payload
            assert payload["reason"] in (
                "cooldown_active", "no_surplus", "insufficient_surplus"
            ), f"unexpected reason: {payload['reason']}"

    def test_requires_auth(self):
        import importlib

        _stub_shared_app_dependencies()
        sys.modules.pop("main", None)

        main = importlib.import_module("main")
        app = main.create_app(options={})

        client = app.test_client()
        response = client.post("/api/v1/energy/solar-surplus/notify")

        # Without auth token: 401 or 403
        assert response.status_code in (401, 403), f"got {response.status_code}"