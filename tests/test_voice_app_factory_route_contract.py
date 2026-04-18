"""Contract tests for create_app() voice route wiring.

The lightweight add-on app factory must expose the public `/api/v1/voice/*`
surface, not only the legacy voice-context helper endpoints.
"""
from __future__ import annotations

import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))


def _stub_create_app_dependencies(monkeypatch):
    """Stub non-voice create_app dependencies that are missing in the smoke env."""
    from flask import Blueprint

    mcp_stub = types.ModuleType("copilot_core.api.v1.mcp")
    mcp_stub.bp = Blueprint("mcp_stub", __name__, url_prefix="/api/v1/mcp")
    monkeypatch.setitem(sys.modules, "copilot_core.api.v1.mcp", mcp_stub)

    tags_stub = types.ModuleType("copilot_core.tags")

    class _TagRegistry:
        pass

    tags_stub.TagRegistry = _TagRegistry
    monkeypatch.setitem(sys.modules, "copilot_core.tags", tags_stub)

    tags_api_stub = types.ModuleType("copilot_core.tags.api")
    tags_api_stub.init_tags_api = lambda registry: None
    monkeypatch.setitem(sys.modules, "copilot_core.tags.api", tags_api_stub)


def test_create_app_registers_public_voice_routes(monkeypatch):
    """`create_app()` must expose the full public voice API surface."""
    _stub_create_app_dependencies(monkeypatch)

    from copilot_core.app import create_app

    app = create_app()
    routes = {rule.rule: rule.methods for rule in app.url_map.iter_rules()}

    expected = {
        "/api/v1/voice/context": "GET",
        "/api/v1/voice/intent": "POST",
        "/api/v1/voice/transcribe": "POST",
        "/api/v1/voice/synthesize": "POST",
        "/api/v1/voice/speak": "POST",
        "/api/v1/voice/status": "GET",
        "/api/v1/voice/audio/<audio_id>": "GET",
        "/api/v1/voice/zones": "GET",
        "/api/v1/voice/intents": "GET",
    }

    for route, method in expected.items():
        assert route in routes, f"Missing route: {route}"
        assert method in routes[route], f"Route {route} missing method {method}"
