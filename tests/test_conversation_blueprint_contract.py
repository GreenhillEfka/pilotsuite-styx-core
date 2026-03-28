"""Regression coverage for conversation blueprint optional-dependency behavior."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.api.v1 import conversation as conversation_module  # noqa: E402
from copilot_core.api.v1.conversation import (  # noqa: E402
    _execute_ha_tool,
    conversation_bp,
    openai_compat_bp,
)


def _client(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(conversation_module, "http_requests", None)

    app = Flask(__name__)
    app.register_blueprint(conversation_bp)
    app.register_blueprint(openai_compat_bp)
    return app.test_client()


def test_conversation_blueprints_stay_available_without_requests(monkeypatch) -> None:
    client = _client(monkeypatch)

    characters = client.get("/chat/characters")
    assert characters.status_code == 200
    assert "characters" in characters.get_json()

    model = client.get("/v1/models/pilotsuite")
    assert model.status_code == 200
    assert model.get_json()["id"] == "pilotsuite"


def test_execute_ha_tool_returns_structured_error_without_requests(monkeypatch) -> None:
    monkeypatch.setattr(conversation_module, "http_requests", None)
    result = _execute_ha_tool("ha.get_states", {})
    assert result["error"] == "ha_http_unavailable"
    assert result["tool"] == "ha.get_states"
