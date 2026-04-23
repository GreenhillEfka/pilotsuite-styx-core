"""Weather API Contract Tests — CORE-HARDEN-216"""
from __future__ import annotations

import sys
from pathlib import Path
from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from flask import Flask
from copilot_core.api.v1.weather import bp as weather_bp
import copilot_core.api.v1.weather as weather_mod


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(weather_bp)
    return app


def _with_auth():
    return patch.object(weather_mod, '_validate_token', return_value=True)


def _make_weather_service():
    mock = MagicMock()
    mock.get_current_weather.return_value = {
        "condition": "sunny", "temperature_c": 22.0,
        "humidity_pct": 55, "wind_speed_kmh": 12.0,
        "precipitation_mm": 0.0, "cloud_cover_pct": 10,
    }
    mock.get_forecast.return_value = {
        "days": [{"date": "2026-04-23", "condition": "sunny", "high_c": 24, "low_c": 14}],
    }
    mock.get_pv_recommendations.return_value = {
        "optimal_charging": True, "surplus_kwh": 3.5, "recommendation": "charge_ev",
    }
    mock._source = "open-meteo"
    mock._cache_time = datetime(2026, 4, 23, 12, 0, 0, tzinfo=timezone.utc)
    return mock


class TestWeatherCurrent:
    """GET /weather/"""

    def test_get_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch.object(weather_mod, 'get_weather_service',
                             return_value=_make_weather_service()):
                r = app.test_client().get("/weather/")
                assert r.status_code == 200, f"got {r.status_code}"

    def test_get_returns_condition(self):
        app = _make_app()
        with _with_auth():
            with patch.object(weather_mod, 'get_weather_service',
                             return_value=_make_weather_service()):
                d = app.test_client().get("/weather/").get_json()
                assert "condition" in d.get("data", {})

    def test_get_requires_auth(self):
        r = _make_app().test_client().get("/weather/")
        assert r.status_code in (401, 403)


class TestWeatherForecast:
    """GET /weather/forecast"""

    def test_get_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch.object(weather_mod, 'get_weather_service',
                             return_value=_make_weather_service()):
                r = app.test_client().get("/weather/forecast")
                assert r.status_code == 200

    def test_get_returns_days(self):
        app = _make_app()
        with _with_auth():
            with patch.object(weather_mod, 'get_weather_service',
                             return_value=_make_weather_service()):
                d = app.test_client().get("/weather/forecast").get_json()
                assert "days" in d.get("data", {}) or "forecast" in d.get("data", {})

    def test_get_requires_auth(self):
        r = _make_app().test_client().get("/weather/forecast")
        assert r.status_code in (401, 403)


class TestWeatherPV:
    """GET /weather/pv-recommendations"""

    def test_get_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch.object(weather_mod, 'get_weather_service',
                             return_value=_make_weather_service()):
                r = app.test_client().get("/weather/pv-recommendations")
                assert r.status_code == 200

    def test_get_requires_auth(self):
        r = _make_app().test_client().get("/weather/pv-recommendations")
        assert r.status_code in (401, 403)


class TestWeatherHealth:
    """GET /weather/health"""

    def test_get_returns_200(self):
        app = _make_app()
        with _with_auth():
            with patch.object(weather_mod, 'get_weather_service',
                             return_value=_make_weather_service()):
                r = app.test_client().get("/weather/health")
                assert r.status_code == 200

    def test_get_returns_ok(self):
        app = _make_app()
        with _with_auth():
            with patch.object(weather_mod, 'get_weather_service',
                             return_value=_make_weather_service()):
                d = app.test_client().get("/weather/health").get_json()
                assert d.get("status") == "ok"

    def test_get_requires_auth(self):
        r = _make_app().test_client().get("/weather/health")
        assert r.status_code in (401, 403)
