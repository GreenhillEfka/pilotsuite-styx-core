"""
Sensor Data API - PilotSuite v7.14.0

API for reading sensor data.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

sensors_bp = Blueprint("sensors", __name__, url_prefix="/api/v1/sensors")


def _get_ha_hass():
    """Get Home Assistant hass instance."""
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except Exception:
        return None


@sensors_bp.route("", methods=["GET"])
@require_token
def list_sensors():
    """List all sensor entities."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "Home Assistant not available"}), 503
    
    try:
        all_states = list(hass.states.async_all())
        sensors = [
            {
                "entity_id": s.entity_id,
                "state": s.state,
                "unit": s.attributes.get("unit_of_measurement"),
                "device_class": s.attributes.get("device_class"),
                "friendly_name": s.attributes.get("friendly_name"),
            }
            for s in all_states if s.domain == "sensor"
        ]
        
        return jsonify({
            "ok": True,
            "sensors": sensors,
            "count": len(sensors),
        })
    except Exception as e:
        logger.error(f"Failed to list sensors: {e}")
        return jsonify({"error": str(e)}), 500


@sensors_bp.route("/<sensor_id>", methods=["GET"])
@require_token
def get_sensor(sensor_id):
    """Get specific sensor value."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "Home Assistant not available"}), 503
    
    try:
        state = hass.states.get(sensor_id)
        if not state:
            return jsonify({"error": "Sensor not found"}), 404
        
        return jsonify({
            "ok": True,
            "entity_id": state.entity_id,
            "state": state.state,
            "unit": state.attributes.get("unit_of_measurement"),
            "device_class": state.attributes.get("device_class"),
            "friendly_name": state.attributes.get("friendly_name"),
            "last_updated": state.last_updated.isoformat() if state.last_updated else None,
        })
    except Exception as e:
        logger.error(f"Failed to get sensor: {e}")
        return jsonify({"error": str(e)}), 500


@sensors_bp.route("/history/<sensor_id>", methods=["GET"])
@require_token
def get_sensor_history(sensor_id):
    """Get sensor history (requires recorder)."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "Home Assistant not available"}), 503
    
    try:
        hours = int(request.args.get("hours", 24))
        from datetime import datetime, timedelta
        start_time = datetime.now() - timedelta(hours=hours)
        
        # Use HA history API
        history = hass.get_domain("recorder")
        if not history:
            return jsonify({"error": "Recorder not available"}), 503
        
        # Return mock for now - real impl would use history API
        return jsonify({
            "ok": True,
            "entity_id": sensor_id,
            "history": [],
            "message": "History requires recorder integration",
        })
    except Exception as e:
        logger.error(f"Failed to get sensor history: {e}")
        return jsonify({"error": str(e)}), 500


@sensors_bp.route("/groups", methods=["GET"])
@require_token
def get_sensor_groups():
    """Get sensor groups by device class."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "Home Assistant not available"}), 503
    
    try:
        all_states = list(hass.states.async_all())
        sensors = [s for s in all_states if s.domain == "sensor"]
        
        groups = {}
        for s in sensors:
            device_class = s.attributes.get("device_class", "other")
            if device_class not in groups:
                groups[device_class] = []
            groups[device_class].append({
                "entity_id": s.entity_id,
                "state": s.state,
                "unit": s.attributes.get("unit_of_measurement"),
            })
        
        return jsonify({
            "ok": True,
            "groups": groups,
        })
    except Exception as e:
        logger.error(f"Failed to get sensor groups: {e}")
        return jsonify({"error": str(e)}), 500
