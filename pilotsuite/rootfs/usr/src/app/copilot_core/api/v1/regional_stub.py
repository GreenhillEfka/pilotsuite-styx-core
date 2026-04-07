"""Regional API stub — returns empty/placeholder data.

HA sensors (tariff, weather_warning, battery_optimizer, proactive_alert,
heat_pump, fuel_price, gas_meter, ev_charging, energy_forecast) all call
/api/v1/regional. Without this stub they get 404 every polling cycle.
"""
from flask import Blueprint, jsonify, request

from copilot_core.api.security import validate_token as _validate_token

regional_stub_bp = Blueprint("regional_stub", __name__, url_prefix="/api/v1/regional")


@regional_stub_bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized"}), 401


@regional_stub_bp.get("/")
def regional_root():
    """Regional overview — stub."""
    return jsonify({
        "ok": True,
        "status": "not_configured",
        "message": "Regional services not yet configured",
        "tariff": None,
        "fuel_prices": None,
        "weather_warnings": [],
        "demand_response": None,
    })
