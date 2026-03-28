"""Regression coverage for weather blueprint optional-dependency behavior."""

from __future__ import annotations

from pathlib import Path
import sys

from flask import Flask


REPO_ROOT = Path(__file__).resolve().parents[1]
CORE_APP_ROOT = REPO_ROOT / "copilot_core" / "rootfs" / "usr" / "src" / "app"

path_str = str(CORE_APP_ROOT)
if CORE_APP_ROOT.exists() and path_str not in sys.path:
    sys.path.insert(0, path_str)


from copilot_core.api.v1 import weather as weather_module  # noqa: E402
from copilot_core.api.v1.weather import bp as weather_bp, init_weather_api  # noqa: E402


def _client(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    monkeypatch.setattr(weather_module, "http_requests", None)
    init_weather_api(lat=52.5, lon=13.4)

    app = Flask(__name__)
    app.register_blueprint(weather_bp)
    return app.test_client()


def test_weather_blueprint_falls_back_cleanly_without_requests(monkeypatch) -> None:
    client = _client(monkeypatch)
    headers = {"Authorization": "Bearer test-token"}

    current = client.get("/weather/", headers=headers)
    assert current.status_code == 200
    current_body = current.get_json()
    assert current_body["status"] == "ok"
    assert current_body["data"]["source"] == "fallback"

    forecast = client.get("/weather/forecast?days=2", headers=headers)
    assert forecast.status_code == 200
    forecast_body = forecast.get_json()
    assert forecast_body["status"] == "ok"
    assert all(day["source"] == "fallback" for day in forecast_body["data"]["forecast"])

    pv = client.get("/weather/pv-recommendations", headers=headers)
    assert pv.status_code == 200
    assert pv.get_json()["status"] == "ok"

    health = client.get("/weather/health", headers=headers)
    assert health.status_code == 200
    assert health.get_json()["service"] == "weather"
