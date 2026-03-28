"""Regression coverage for Styx voice optional-dependency behavior."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.api.v1 import styx_voice as styx_voice_module  # noqa: E402
from copilot_core.api.v1.styx_voice import styx_voice_bp  # noqa: E402


def _client(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(styx_voice_module, "http_requests", None)

    app = Flask(__name__)
    app.register_blueprint(styx_voice_bp)
    return app.test_client()


def test_styx_voice_status_stays_available_without_requests(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    response = client.get("/api/v1/styx/voice/status", headers=headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["stt"]["available"] is False
    assert "requests" in body["stt"]["error"]


def test_styx_voice_stt_degrades_without_requests(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token", "Content-Type": "audio/wav"}

    response = client.post("/api/v1/styx/stt", headers=headers, data=b"fakewav")
    assert response.status_code == 503
    assert response.get_json()["error"] == "styx_voice_http_unavailable"
