from __future__ import annotations

"""Contract tests for helper-backed voice health HTTP surfaces."""

import sys
import types
from pathlib import Path

import pytest
from flask import Blueprint

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))


def _stub_create_app_dependencies(monkeypatch):
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


class _DummyChecker:
    async def full_health_check(self):
        return {"status": "healthy", "components": {}}

    async def get_quick_health(self):
        return {"status": "healthy", "components": {}}

    async def get_dependency_health(self):
        return {"status": "healthy", "missing_required": []}


def _make_client(monkeypatch, voice_block):
    _stub_create_app_dependencies(monkeypatch)
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "pilotclaw-test-token")

    from copilot_core import app as app_module
    from copilot_core.api.v1 import metrics as metrics_api
    from copilot_core.voice import voice_health

    monkeypatch.setattr(metrics_api, "get_health_checker", lambda: _DummyChecker())
    monkeypatch.setattr(metrics_api, "get_voice_health_block", lambda: dict(voice_block))
    monkeypatch.setattr(voice_health, "get_voice_health_block", lambda: dict(voice_block))

    app = app_module.create_app()
    return app.test_client()


@pytest.mark.parametrize(
    "voice_block",
    [
        {
            "can_transcribe": False,
            "can_synthesize": True,
            "can_speak": True,
            "can_dialog": False,
            "available_backends": [
                {"type": "tts", "backend": "piper", "status": "available"},
            ],
            "components": {
                "intent_handler": "unavailable",
                "mood_engine": "unavailable",
                "habitus_service": "unavailable",
                "context_builder": "unavailable",
                "proactive_hints": "unavailable",
                "stt_engine": "unavailable",
                "tts_engine": "available",
                "nlu_engine": "unavailable",
            },
            "runtime": {
                "stt": {
                    "available": False,
                    "engine": "whisper",
                    "available_backends": [],
                },
                "tts": {
                    "available": True,
                    "engine": "piper",
                    "available_backends": ["piper"],
                },
                "nlu": {
                    "available": False,
                    "engine": "rule_based",
                    "supported_languages": ["de", "en"],
                },
            },
        },
        {
            "can_transcribe": True,
            "can_synthesize": False,
            "can_speak": False,
            "can_dialog": False,
            "available_backends": [
                {"type": "stt", "backend": "whisper", "status": "available"},
            ],
            "components": {
                "intent_handler": "unavailable",
                "mood_engine": "unavailable",
                "habitus_service": "unavailable",
                "context_builder": "unavailable",
                "proactive_hints": "unavailable",
                "stt_engine": "available",
                "tts_engine": "unavailable",
                "nlu_engine": "unavailable",
            },
            "runtime": {
                "stt": {
                    "available": True,
                    "engine": "whisper",
                    "available_backends": ["whisper"],
                },
                "tts": {
                    "available": False,
                    "engine": "piper",
                    "available_backends": [],
                },
                "nlu": {
                    "available": False,
                    "engine": "rule_based",
                    "supported_languages": ["de", "en"],
                },
            },
        },
    ],
)
def test_helper_backed_health_surfaces_preserve_partial_voice_truth(monkeypatch, voice_block):
    client = _make_client(monkeypatch, voice_block)
    headers = {"X-Auth-Token": "pilotclaw-test-token"}

    assert client.get("/health", headers=headers).get_json()["voice"] == voice_block
    assert client.get("/api/v1/status", headers=headers).get_json()["voice"] == voice_block
    assert client.get("/api/v1/ready", headers=headers).get_json()["voice"] == voice_block
