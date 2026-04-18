from __future__ import annotations

"""Contract tests for voice discovery surface parity.

These checks keep the app-level capabilities endpoint and the repo-root REST
registry aligned with the restored public voice runtime surface.
"""

import importlib
import pytest

import os
import sys
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))

from flask import Blueprint

from copilot_core.api.rest_api import RESTAPI
from copilot_core.api.voice_discovery import VOICE_DISCOVERY_ENDPOINTS, voice_capabilities_module

def _stub_create_app_dependencies(monkeypatch):
    mcp_stub = types.ModuleType("copilot_core.api.v1.mcp")
    mcp_stub.bp = Blueprint("mcp_stub", __name__, url_prefix="/api/v1/mcp")
    monkeypatch.setitem(sys.modules, "copilot_core.api.v1.mcp", mcp_stub)

    tags_stub = types.ModuleType("copilot_core.tags")

    class _TagRegistry:
        pass

    tags_stub.TagRegistry = _TagRegistry
    tags_stub.create_tag_service = lambda *args, **kwargs: None
    monkeypatch.setitem(sys.modules, "copilot_core.tags", tags_stub)

    tags_api_stub = types.ModuleType("copilot_core.tags.api")
    tags_api_stub.init_tags_api = lambda registry: None
    monkeypatch.setitem(sys.modules, "copilot_core.tags.api", tags_api_stub)

def test_voice_capabilities_module_advertises_restored_public_routes():
    payload = voice_capabilities_module()

    assert payload["enabled"] is True
    assert payload["status_surface"] == "/api/v1/voice/status"
    assert payload["endpoints"] == list(VOICE_DISCOVERY_ENDPOINTS)
    assert "/api/v1/voice/context" not in payload["endpoints"]
    assert "capability-gated consumer branching" in payload["features"]

def test_create_app_capabilities_surface_keeps_one_canonical_voice_module_route(monkeypatch):
    _stub_create_app_dependencies(monkeypatch)
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "pilotclaw-test-token")

    from copilot_core.app import create_app

    app = create_app()
    capability_rules = [rule.endpoint for rule in app.url_map.iter_rules() if rule.rule == "/api/v1/capabilities"]
    assert capability_rules == ["api_v1.dev.get_capabilities"]

    client = app.test_client()
    unauthorized = client.get("/api/v1/capabilities")
    assert unauthorized.status_code == 401

    response = client.get("/api/v1/capabilities", headers={"X-Auth-Token": "pilotclaw-test-token"})

    assert response.status_code == 200
    payload = response.get_json()

    assert "voice" in payload["capabilities"]
    assert payload["modules"]["voice"] == voice_capabilities_module()
    assert payload["modules"]["voice_context"]["endpoints"] == ["/api/v1/voice_context"]

def test_main_create_app_capabilities_surface_keeps_one_canonical_voice_module_route(monkeypatch):
    _stub_create_app_dependencies(monkeypatch)
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "pilotclaw-test-token")
    sys.modules.pop("main", None)

    main = importlib.import_module("main")

    app = main.create_app(options={})
    capability_rules = [rule.endpoint for rule in app.url_map.iter_rules() if rule.rule == "/api/v1/capabilities"]
    assert capability_rules == ["dev.get_capabilities"]

    client = app.test_client()
    unauthorized = client.get("/api/v1/capabilities")
    assert unauthorized.status_code == 401

    response = client.get("/api/v1/capabilities", headers={"X-Auth-Token": "pilotclaw-test-token"})

    assert response.status_code == 200
    payload = response.get_json()

    assert payload["modules"]["voice"] == voice_capabilities_module()
    assert payload["modules"]["voice_context"]["endpoints"] == ["/api/v1/voice_context"]


def test_rest_api_voice_registry_matches_public_discovery_surface():
    api = RESTAPI()
    voice_endpoints = {(endpoint.path, endpoint.method) for endpoint in api.get_endpoints("voice")}

    expected = {
        ("/api/v1/voice/intent", "POST"),
        ("/api/v1/voice/transcribe", "POST"),
        ("/api/v1/voice/synthesize", "POST"),
        ("/api/v1/voice/speak", "POST"),
        ("/api/v1/voice/status", "GET"),
        ("/api/v1/voice/audio/{audio_id}", "GET"),
        ("/api/v1/voice/zones", "GET"),
        ("/api/v1/voice/intents", "GET"),
    }

    assert expected.issubset(voice_endpoints)
    assert ("/api/v1/voice/process", "POST") not in voice_endpoints
