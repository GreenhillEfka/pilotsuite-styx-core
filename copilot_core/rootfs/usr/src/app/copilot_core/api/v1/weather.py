"""
Weather API - PilotSuite v7.23.0

API for weather data and forecasts.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

weather_bp = Blueprint("weather", __name__, url_prefix="/api/v1/weather")


def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except Exception:
        return None


@weather_bp.route("", methods=["GET"])
@require_token
def list_weather():
    """List all weather entities."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        weather_entities = [s for s in hass.states.async_all() if s.domain == "weather"]
        return jsonify({
            "ok": True,
            "weather": [
                {
                    "entity_id": w.entity_id,
                    "state": w.state,
                    "temperature": w.attributes.get("temperature"),
                    "humidity": w.attributes.get("humidity"),
                    "pressure": w.attributes.get("pressure"),
                    "wind_speed": w.attributes.get("wind_speed"),
                    "forecast": w.attributes.get("forecast", [])[:5],
                    "friendly_name": w.attributes.get("friendly_name"),
                }
                for w in weather_entities
            ],
            "count": len(weather_entities),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@weather_bp.route("/<weather_id>", methods=["GET"])
@require_token
def get_weather(weather_id):
    """Get specific weather entity."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    
    try:
        state = hass.states.get(weather_id)
        if not state or state.domain != "weather":
            return jsonify({"error": "Weather entity not found"}), 404
        
        return jsonify({
            "ok": True,
            "entity_id": state.entity_id,
            "state": state.state,
            "temperature": state.attributes.get("temperature"),
            "humidity": state.attributes.get("humidity"),
            "pressure": state.attributes.get("pressure"),
            "wind_speed": state.attributes.get("wind_speed"),
            "wind_bearing": state.attributes.get("wind_bearing"),
            "forecast": state.attributes.get("forecast", [])[:10],
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500
