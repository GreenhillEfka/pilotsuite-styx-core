"""Weather API — Slice 221 (CORE ONLY)."""
from __future__ import annotations
import logging
from flask import Blueprint, jsonify
_LOGGER = logging.getLogger(__name__)
bp = Blueprint("weather", __name__, url_prefix="/api/v1")
@bp.get("/weather/forecast")
def get_weather_forecast():
    return jsonify({"ok": True, "forecast": []})
@bp.get("/weather/alerts")
def get_weather_alerts():
    return jsonify({"ok": True, "alerts": []})
@bp.get("/weather/current")
def get_weather_current():
    return jsonify({"ok": True, "current": {}})
