"""
Devices API - PilotSuite v7.33
"""

from flask import Blueprint, jsonify
from copilot_core.api.security import require_token

devices_bp = Blueprint("devices", __name__, url_prefix="/api/v1/devices")

def _get_ha_hass():
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except:
        return None

@devices_bp.route("", methods=["GET"])
@require_token
def list_devices():
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "HA not available"}), 503
    from homeassistant.helpers import device_registry as dr
    reg = dr.async_get(hass)
    devices = reg.devices
    return jsonify({"ok": True, "devices": [{"id": d.id, "name": d.name, "identifiers": list(d.identifiers)} for d in devices.values()], "count": len(devices)})
