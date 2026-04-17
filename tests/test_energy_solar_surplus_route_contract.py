"""Route contract tests for solar-surplus batch recommendations (VFM-012 Slice 012-D)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

mock_security = MagicMock()
mock_security.require_token = lambda f: f
sys.modules["copilot_core.api.security"] = mock_security

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.insert(0, str(ADDON_APP))

from flask import Flask
from copilot_core.api.v1 import energy_forecast as ef


def _make_app():
    app = Flask(__name__)
    app.register_blueprint(ef.energy_forecast_bp)
    return app


class TestSolarSurplusRecommendationRoute:
    def test_route_returns_normalized_recommendation_batch(self):
        app = _make_app()
        client = app.test_client()

        payload = {
            "reference_time": "2026-04-17T09:05:00Z",
            "now": "2026-04-17T09:05:00Z",
            "pv_forecast": [
                {"timestamp": "2026-04-17T10:00:00Z", "pv_power_kw": 2.4, "window_hours": 1.0, "confidence": 0.92},
                {"timestamp": "2026-04-17T11:00:00Z", "pv_power_kw": 2.8, "window_hours": 1.0, "confidence": 0.9},
                {"timestamp": "2026-04-17T12:00:00Z", "pv_power_kw": 3.6, "window_hours": 1.0, "confidence": 0.94},
            ],
            "load_forecast": [
                {"timestamp": "2026-04-17T10:00:00Z", "predicted_consumption_kwh": 0.5, "confidence": 0.88},
                {"timestamp": "2026-04-17T11:00:00Z", "predicted_consumption_kwh": 0.7, "confidence": 0.88},
                {"timestamp": "2026-04-17T12:00:00Z", "predicted_consumption_kwh": 0.6, "confidence": 0.88},
            ],
            "price_forecast": [
                {"timestamp": "2026-04-17T10:00:00Z", "price_ct_kwh": 26.0, "export_price_ct_kwh": 8.0},
                {"timestamp": "2026-04-17T11:00:00Z", "price_ct_kwh": 29.0, "export_price_ct_kwh": 8.0},
                {"timestamp": "2026-04-17T12:00:00Z", "price_ct_kwh": 32.0, "export_price_ct_kwh": 8.0},
            ],
            "shiftable_devices": [
                {
                    "device_id": "dishwasher-1",
                    "device_type": "dishwasher",
                    "name": "Dishwasher",
                    "power_kw": 1.2,
                    "energy_kwh": 1.2,
                    "duration_hours": 1.0,
                    "flexibility_hours": 6,
                    "priority": 2,
                    "min_start_hour": 10,
                    "max_start_hour": 14,
                    "must_complete_by": "2026-04-17T15:00:00Z",
                    "current_state": "idle",
                    "cost_per_kwh": 29.0,
                }
            ],
        }

        response = client.post("/api/v1/energy/solar-surplus/recommendations", json=payload)

        assert response.status_code == 200, response.get_data(as_text=True)
        data = response.get_json()
        assert data["ok"] is True
        assert data["generated_at"] == "2026-04-17T09:05:00Z"
        assert set(data) == {"ok", "generated_at", "summary", "recommendations", "slots", "candidates"}

        assert data["summary"]["total_slots"] == 3
        assert data["summary"]["total_candidates"] == 1
        assert data["summary"]["recommendations_count"] == 1

        assert len(data["slots"]) == 3
        assert data["slots"][0]["timestamp"] == "2026-04-17T10:00:00Z"
        assert data["slots"][0]["available_surplus_kwh"] == 1.9

        assert len(data["candidates"]) == 1
        assert data["candidates"][0]["device_id"] == "dishwasher-1"
        assert data["candidates"][0]["earliest_start"] == "2026-04-17T10:00:00Z"

        assert len(data["recommendations"]) == 1
        recommendation = data["recommendations"][0]
        assert recommendation["device_id"] == "dishwasher-1"
        assert recommendation["action"] == "schedule_at"
        assert recommendation["recommended_start"] == "2026-04-17T12:00:00Z"
        assert recommendation["slot_timestamp"] == "2026-04-17T12:00:00Z"
        assert recommendation["expected_grid_relief_kwh"] == 1.2

    def test_route_rejects_missing_pv_forecast_list(self):
        app = _make_app()
        client = app.test_client()

        response = client.post(
            "/api/v1/energy/solar-surplus/recommendations",
            json={"shiftable_devices": []},
        )

        assert response.status_code == 400
        assert response.get_json()["error"] == "Field 'pv_forecast' must be a list"

    def test_route_rejects_invalid_reference_time(self):
        app = _make_app()
        client = app.test_client()

        response = client.post(
            "/api/v1/energy/solar-surplus/recommendations",
            json={
                "reference_time": "tomorrow-ish",
                "pv_forecast": [],
                "shiftable_devices": [],
            },
        )

        assert response.status_code == 400
        assert response.get_json()["error"] == "Field 'reference_time' must be a valid ISO-8601 timestamp"
