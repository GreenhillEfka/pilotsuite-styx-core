"""Energy Forecast API Contract Tests — Slice 370"""
from __future__ import annotations
import sys
from pathlib import Path
from unittest.mock import MagicMock

# Mock security module BEFORE importing energy_forecast
mock_security = MagicMock()
mock_security.require_token = lambda f: f  # passthrough decorator
sys.modules["copilot_core.api.security"] = mock_security

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from flask import Flask
from copilot_core.api.v1 import energy_forecast as ef


def _make_energy_app():
    app = Flask(__name__)
    app.register_blueprint(ef.energy_forecast_bp)
    return app


class TestEnergyForecastQueryValidation:
    """Slice 370: energy_forecast.py query param int/float validation."""

    def test_optimization_windows_rejects_non_integer_hours(self):
        app = _make_energy_app()
        client = app.test_client()
        for bad in ("abc", "12.5", "null", ""):
            r = client.get(f"/api/v1/energy/load-shifting/windows?hours={bad}")
            assert r.status_code == 400, f"hours={bad!r} -> {r.status_code}"

    def test_consumption_forecast_rejects_non_integer_hours(self):
        app = _make_energy_app()
        client = app.test_client()
        for bad in ("xyz", "24.0"):
            r = client.get(f"/api/v1/energy/forecast/consumption?hours={bad}")
            assert r.status_code == 400, f"hours={bad!r} -> {r.status_code}"

    def test_pv_forecast_rejects_non_integer_hours(self):
        app = _make_energy_app()
        client = app.test_client()
        for bad in ("abc", "36.6"):
            r = client.get(f"/api/v1/energy/forecast/pv?hours={bad}")
            assert r.status_code == 400, f"hours={bad!r} -> {r.status_code}"

    def test_pv_forecast_rejects_non_numeric_peak_kw(self):
        app = _make_energy_app()
        client = app.test_client()
        r = client.get("/api/v1/energy/forecast/pv?peak_kw=not_a_number")
        assert r.status_code == 400, f"peak_kw=bad -> {r.status_code}"

    def test_pv_forecast_rejects_non_numeric_azimuth(self):
        app = _make_energy_app()
        client = app.test_client()
        r = client.get("/api/v1/energy/forecast/pv?azimuth=bad")
        assert r.status_code == 400, f"azimuth=bad -> {r.status_code}"

    def test_pv_forecast_rejects_non_numeric_tilt(self):
        app = _make_energy_app()
        client = app.test_client()
        r = client.get("/api/v1/energy/forecast/pv?tilt=twenty")
        assert r.status_code == 400, f"tilt=twenty -> {r.status_code}"

    def test_combined_forecast_rejects_non_integer_hours(self):
        app = _make_energy_app()
        client = app.test_client()
        for bad in ("abc", "yes"):
            r = client.get(f"/api/v1/energy/forecast/combined?hours={bad}")
            assert r.status_code == 400, f"hours={bad!r} -> {r.status_code}"
