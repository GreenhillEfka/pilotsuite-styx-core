"""
Service Call API - PilotSuite v7.14.0

API for calling HA services directly.
"""

from flask import Blueprint, jsonify, request
import logging

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

services_bp = Blueprint("services", __name__, url_prefix="/api/v1/services")


def _get_ha_hass():
    """Get Home Assistant hass instance."""
    try:
        from homeassistant.core import HomeAssistant
        return HomeAssistant.get()
    except Exception:
        return None


@services_bp.route("/list", methods=["GET"])
@require_token
def list_services():
    """List all available HA services."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "Home Assistant not available"}), 503
    
    try:
        services = hass.services.services
        return jsonify({
            "ok": True,
            "services": services,
        })
    except Exception as e:
        logger.error(f"Failed to list services: {e}")
        return jsonify({"error": str(e)}), 500


@services_bp.route("/call/<domain>/<service>", methods=["POST"])
@require_token
def call_service(domain, service):
    """Call a specific HA service."""
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "Home Assistant not available"}), 503
    
    data = request.get_json() or {}
    
    try:
        hass.services.call(domain, service, data)
        return jsonify({
            "ok": True,
            "domain": domain,
            "service": service,
            "data": data,
        })
    except Exception as e:
        logger.error(f"Failed to call service: {e}")
        return jsonify({"error": str(e)}), 500


@services_bp.route("/call", methods=["POST"])
@require_token
def call_service_post():
    """Call service with JSON body."""
    data = request.get_json() or {}
    domain = data.get("domain")
    service = data.get("service")
    service_data = data.get("data", {})
    
    if not domain or not service:
        return jsonify({"error": "domain and service required"}), 400
    
    hass = _get_ha_hass()
    if not hass:
        return jsonify({"error": "Home Assistant not available"}), 503
    
    try:
        hass.services.call(domain, service, service_data)
        return jsonify({
            "ok": True,
            "domain": domain,
            "service": service,
        })
    except Exception as e:
        logger.error(f"Failed to call service: {e}")
        return jsonify({"error": str(e)}), 500
