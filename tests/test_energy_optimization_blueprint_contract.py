"""Contract coverage for the Slice 13 energy optimization API surface."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from flask import Flask

from copilot_core.api.v1.energy_forecast import energy_forecast_bp
from copilot_core.energy.optimization_engine import create_energy_optimization_engine


def _client(monkeypatch):
    monkeypatch.setenv("COPILOT_AUTH_TOKEN", "test-token")
    app = Flask(__name__)
    app.config["COPILOT_ENERGY_OPTIMIZATION_ENGINE"] = create_energy_optimization_engine()
    app.register_blueprint(energy_forecast_bp)
    return app.test_client()


def _headers() -> dict[str, str]:
    return {"Authorization": "Bearer test-token"}


def _recent_peak_timestamp() -> str:
    now = datetime.now(timezone.utc)
    candidate = now.replace(hour=18, minute=0, second=0, microsecond=0)
    for _ in range(7):
        if candidate.weekday() < 5 and candidate <= now + timedelta(days=1):
            return candidate.isoformat().replace("+00:00", "Z")
        candidate -= timedelta(days=1)
    return now.isoformat().replace("+00:00", "Z")


def _seed_peak_reading(client) -> str:
    response = client.post(
        "/api/v1/energy/optimization/readings",
        headers=_headers(),
        json={
            "entity_id": "sensor.power_washer",
            "zone_id": "zone_laundry",
            "module_id": "energy_laundry",
            "value": 1800.0,
            "unit": "W",
            "timestamp": _recent_peak_timestamp(),
            "cost": 0.63,
            "tariff_rate": "peak",
        },
    )
    assert response.status_code == 200
    body = response.get_json()
    assert body["accepted"] == 1
    assert body["created_suggestions"] == 1

    suggestions = client.get("/api/v1/energy/optimization/suggestions", headers=_headers())
    suggestion_body = suggestions.get_json()
    assert suggestion_body["count"] == 1
    return suggestion_body["suggestions"][0]["suggestion_id"]


def test_optimization_summary_and_shifting_surface(monkeypatch) -> None:
    client = _client(monkeypatch)
    _seed_peak_reading(client)

    summary_response = client.get(
        "/api/v1/energy/optimization/summary?hours=240&zone_id=zone_laundry",
        headers=_headers(),
    )
    assert summary_response.status_code == 200
    summary_body = summary_response.get_json()
    assert summary_body["summary"]["zone_consumption"]["zone_laundry"] == 1800.0
    assert summary_body["summary"]["module_consumption"]["energy_laundry"] == 1800.0
    assert summary_body["savings"]["potential_savings_eur"] > 0

    shifting_response = client.get("/api/v1/energy/shifting", headers=_headers())
    assert shifting_response.status_code == 200
    shifting_body = shifting_response.get_json()
    assert shifting_body["count"] == 1
    assert shifting_body["opportunities"][0]["optimization_type"] == "schedule_shift"


def test_explain_accept_and_report_surface(monkeypatch) -> None:
    client = _client(monkeypatch)
    suggestion_id = _seed_peak_reading(client)

    explain_response = client.get(f"/api/v1/energy/explain/{suggestion_id}", headers=_headers())
    assert explain_response.status_code == 200
    explain_body = explain_response.get_json()
    assert explain_body["policy_gate_required"] is True
    assert "Erwartete Ersparnis" in explain_body["explanation"]

    accept_response = client.post(
        f"/api/v1/energy/optimization/suggestions/{suggestion_id}/accept",
        headers=_headers(),
    )
    assert accept_response.status_code == 200
    assert accept_response.get_json()["suggestion"]["accepted"] is True

    report_response = client.get(
        "/api/v1/energy/reports/generate?hours=240&budget_eur=1.5",
        headers=_headers(),
    )
    assert report_response.status_code == 200
    report_body = report_response.get_json()["report"]
    assert report_body["savings"]["accepted_count"] == 1
    assert report_body["savings"]["realized_savings_eur"] > 0
    assert report_body["budget"]["status"] == "within_budget"


def test_cost_and_budget_endpoints_use_live_summary(monkeypatch) -> None:
    client = _client(monkeypatch)
    _seed_peak_reading(client)

    costs_response = client.get("/api/v1/energy/costs?hours=240", headers=_headers())
    assert costs_response.status_code == 200
    costs_body = costs_response.get_json()
    assert costs_body["costs"]["total_cost_eur"] == 0.63
    assert costs_body["costs"]["total_consumption_kwh"] == 1.8
    assert costs_body["current_tariff"] is not None

    budget_response = client.get(
        "/api/v1/energy/costs/budget?hours=240&budget_eur=1.0",
        headers=_headers(),
    )
    assert budget_response.status_code == 200
    budget_body = budget_response.get_json()["budget"]
    assert budget_body["spent_eur"] == 0.63
    assert budget_body["remaining_eur"] == 0.37
    assert budget_body["status"] == "within_budget"

    summary_response = client.get(
        "/api/v1/energy/costs/summary?hours=240&budget_eur=1.0",
        headers=_headers(),
    )
    assert summary_response.status_code == 200
    summary_body = summary_response.get_json()
    assert summary_body["summary"]["total_cost"] == 0.63
    assert summary_body["savings"]["unresolved_count"] == 1
