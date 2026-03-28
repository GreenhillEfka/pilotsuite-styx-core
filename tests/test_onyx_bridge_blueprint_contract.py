"""Regression coverage for Onyx bridge optional-dependency behavior."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.api.v1 import onyx_bridge as onyx_bridge_module  # noqa: E402
from copilot_core.api.v1.onyx_bridge import onyx_bridge_bp  # noqa: E402


def _client(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("SUPERVISOR_TOKEN", "ha-token")
    monkeypatch.setattr(onyx_bridge_module, "http_requests", None)

    app = Flask(__name__)
    app.register_blueprint(onyx_bridge_bp)
    return app.test_client()


def test_onyx_status_stays_available_without_requests(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    response = client.get("/api/v1/onyx/status", headers=headers)
    assert response.status_code == 200
    body = response.get_json()
    assert body["ok"] is True
    assert body["ha_reachable"] is False
    assert "requests" in body["ha_error"]


def test_onyx_service_call_degrades_without_requests(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    response = client.post(
        "/api/v1/onyx/ha/service-call",
        headers=headers,
        json={"domain": "light", "service": "turn_on", "service_data": {"entity_id": "light.kueche"}},
    )
    assert response.status_code == 503
    assert response.get_json()["error"] == "onyx_bridge_unavailable"
