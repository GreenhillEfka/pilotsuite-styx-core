"""Contract tests for automation suggestions generated from solar-surplus batches (VFM-012 Slice 012-E)."""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

mock_security = MagicMock()
mock_security.require_api_key = lambda f: f
sys.modules["copilot_core.api.security"] = mock_security

ROOT = Path(__file__).resolve().parents[1]
ADDON_APP = ROOT / "addons" / "pilotsuite" / "app"
if str(ADDON_APP) not in sys.path:
    sys.path.append(str(ADDON_APP))

from flask import Flask
from copilot_core.automations import api as automations_api
from copilot_core.automations.suggestion_engine import AutomationSuggestionEngine


def _make_app():
    app = Flask(__name__)
    automations_api.init_automations_api(AutomationSuggestionEngine())
    app.register_blueprint(automations_api.automations_bp)
    return app


class TestAutomationSolarSurplusGenerateRoute:
    def test_generate_route_turns_solar_surplus_batch_into_energy_suggestion(self):
        app = _make_app()
        client = app.test_client()

        payload = {
            "solar_surplus_batches": [
                {
                    "reference_time": "2026-04-17T09:05:00Z",
                    "now": "2026-04-17T09:05:00Z",
                    "pv_forecast": [
                        {"timestamp": "2026-04-17T10:00:00Z", "pv_power_kw": 2.4, "window_hours": 1.0, "confidence": 0.92},
                        {"timestamp": "2026-04-17T11:00:00Z", "pv_power_kw": 2.8, "window_hours": 1.0, "confidence": 0.90},
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
                            "entity_id": "switch.dishwasher",
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
            ]
        }

        response = client.post("/api/v1/automations/generate", json=payload)

        assert response.status_code == 201, response.get_data(as_text=True)
        data = response.get_json()
        assert data["ok"] is True
        assert data["generated"] == 1
        assert len(data["ids"]) == 1
        assert len(data["solar_surplus_batches"]) == 1

        batch = data["solar_surplus_batches"][0]
        assert batch["summary"]["recommendations_count"] == 1
        assert batch["generated"] == 1
        assert batch["suggestion_ids"] == data["ids"]
        assert batch["recommendations"][0]["action"] == "schedule_at"
        assert batch["recommendations"][0]["recommended_start"] == "2026-04-17T12:00:00Z"

        suggestions = client.get("/api/v1/automations/suggestions").get_json()
        assert suggestions["count"] == 1
        suggestion = suggestions["suggestions"][0]
        assert suggestion["category"] == "energy"
        assert suggestion["title"] == "Dishwasher im PV-Fenster um 12:00 starten"
        assert suggestion["source_pattern"] == "solar-surplus:dishwasher-1:schedule_at:12:00"
        assert suggestion["automation_yaml"]["trigger"][0]["at"] == "12:00:00"
        assert suggestion["automation_yaml"]["condition"][0]["entity_id"] == "sensor.pilotsuite_solar_surplus_kwh"
        assert suggestion["automation_yaml"]["condition"][0]["above"] == 1.2
        assert suggestion["automation_yaml"]["action"][0]["service"] == "homeassistant.turn_on"
        assert suggestion["automation_yaml"]["action"][0]["target"]["entity_id"] == "switch.dishwasher"

    def test_generate_route_keeps_batch_report_when_no_shiftable_recommendation_is_actionable(self):
        app = _make_app()
        client = app.test_client()

        payload = {
            "solar_surplus_batches": [
                {
                    "reference_time": "2026-04-17T09:05:00Z",
                    "now": "2026-04-17T09:05:00Z",
                    "pv_forecast": [
                        {"timestamp": "2026-04-17T10:00:00Z", "pv_power_kw": 0.2, "window_hours": 1.0, "confidence": 0.92},
                    ],
                    "load_forecast": [
                        {"timestamp": "2026-04-17T10:00:00Z", "predicted_consumption_kwh": 0.15, "confidence": 0.88},
                    ],
                    "shiftable_devices": [
                        {
                            "device_id": "dryer-1",
                            "entity_id": "switch.dryer",
                            "device_type": "dryer",
                            "name": "Dryer",
                            "energy_kwh": 1.5,
                            "duration_hours": 1.0,
                            "flexibility_hours": 3,
                            "priority": 2,
                            "min_start_hour": 10,
                            "max_start_hour": 12,
                        }
                    ],
                }
            ]
        }

        response = client.post("/api/v1/automations/generate", json=payload)

        assert response.status_code == 201, response.get_data(as_text=True)
        data = response.get_json()
        assert data["ok"] is True
        assert data["generated"] == 0
        assert data["ids"] == []

        batch = data["solar_surplus_batches"][0]
        assert batch["summary"]["recommendations_count"] == 0
        assert batch["generated"] == 0
        assert batch["suggestion_ids"] == []
        assert batch["recommendations"][0]["action"] in {"delay", "do_not_shift"}

        suggestions = client.get("/api/v1/automations/suggestions").get_json()
        assert suggestions["count"] == 0
