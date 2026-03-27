"""Regression coverage for HomeKit blueprint optional-dependency behavior."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.api.v1 import homekit as homekit_module  # noqa: E402
from copilot_core.api.v1.homekit import homekit_bp  # noqa: E402


def _client(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    monkeypatch.setenv("SUPERVISOR_TOKEN", "super-secret")
    monkeypatch.setattr(homekit_module, "http_requests", None)
    monkeypatch.setattr(homekit_module, "_homekit_zones", {})

    app = Flask(__name__)
    app.register_blueprint(homekit_bp)
    return app.test_client()


def test_homekit_blueprint_stays_available_without_requests(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    status_response = client.get("/api/v1/homekit/status", headers=headers)
    assert status_response.status_code == 200
    assert status_response.get_json()["total_zones"] == 0

    toggle_response = client.post(
        "/api/v1/homekit/toggle",
        headers=headers,
        json={
            "zone_id": "zone:wohnzimmer",
            "zone_name": "Wohnzimmer",
            "entity_ids": ["light.wohnzimmer_decke", "sensor.wohnzimmer_temp"],
            "enabled": True,
        },
    )
    assert toggle_response.status_code == 200
    body = toggle_response.get_json()
    assert body["success"] is True
    assert body["entities_exposed"] == 2

    status_after = client.get("/api/v1/homekit/status", headers=headers)
    assert status_after.status_code == 200
    assert status_after.get_json()["total_zones"] == 1
