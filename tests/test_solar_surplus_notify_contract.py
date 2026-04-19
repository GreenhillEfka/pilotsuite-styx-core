"""Contract tests for POST /api/v1/energy/solar-surplus/notify (F2.5-G3)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock
from functools import wraps

# Bypass auth before any app imports
mock_security = MagicMock()

def _mock_require_token(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

mock_security.require_token = _mock_require_token
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

    def test_requires_auth(self, tmp_path, monkeypatch):
        import importlib

        monkeypatch.setattr(
            "copilot_core.api.v1.energy_forecast._SURPLUS_LAST_TRIGGERED_MS",
            None,
        )
        _stub_shared_app_dependencies()

        mods = [k for k in sys.modules if k.startswith("copilot_core.api.v1.energy")]
        for m in mods:
            sys.modules.pop(m, None)
        sys.modules.pop("main", None)

        main = importlib.import_module("main")
        app = main.create_app(options={})

        client = app.test_client()
        response = client.post("/api/v1/energy/solar-surplus/notify")

        assert response.status_code in (401, 403), f"got {response.status_code}"

    def test_returns_json_structure(self, tmp_path, monkeypatch):
        import importlib

        monkeypatch.setattr(
            "copilot_core.api.v1.energy_forecast._SURPLUS_LAST_TRIGGERED_MS",
            None,
        )
        _stub_shared_app_dependencies()

        mods = [k for k in sys.modules if k.startswith("copilot_core.api.v1.energy")]
        for m in mods:
            sys.modules.pop(m, None)
        sys.modules.pop("main", None)

        main = importlib.import_module("main")
        app = main.create_app(options={})

        client = app.test_client()
        response = client.post(
            "/api/v1/energy/solar-surplus/notify",
            headers={"X-Auth-Token": "test"},
        )

        assert response.status_code == 200
        payload = response.get_json()
        assert isinstance(payload, dict)
        assert "ok" in payload