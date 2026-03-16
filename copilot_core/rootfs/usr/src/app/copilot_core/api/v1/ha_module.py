"""HomeAssistant Integration Module API — Status und Konfiguration."""

import logging

from flask import Blueprint, current_app, jsonify, request

from copilot_core.api.security import validate_token as _validate_token
from copilot_core.hub.homeassistant_module import HomeAssistantModuleEngine

_LOGGER = logging.getLogger(__name__)

ha_module_bp = Blueprint(
    "ha_module", __name__, url_prefix="/api/v1/modules/homeassistant",
)


@ha_module_bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized", "message": "Valid X-Auth-Token or Bearer token required"}), 401


def _get_engine() -> HomeAssistantModuleEngine:
    """Lazy-init oder bestehende Engine aus COPILOT_SERVICES holen."""
    services = current_app.config.get("COPILOT_SERVICES", {})
    if isinstance(services, dict):
        engine = services.get("ha_module_engine")
        if engine is not None:
            return engine

    if not hasattr(current_app, "_ha_module_engine"):
        current_app._ha_module_engine = HomeAssistantModuleEngine()
    return current_app._ha_module_engine


# -- GET /status -------------------------------------------------------------

@ha_module_bp.route("/status", methods=["GET"])
def get_status():
    """Gibt den vollstaendigen Modul-Status zurueck."""
    try:
        engine = _get_engine()
        dashboard = engine.get_status()
        return jsonify({
            "status": "ok",
            "module": "homeassistant",
            "connection": dashboard.connection,
            "event_forwarding": dashboard.event_forwarding,
            "webhook": dashboard.webhook,
            "supervisor": dashboard.supervisor,
            "integration_entity_count": dashboard.integration_entity_count,
            "module_count": dashboard.module_count,
            "active_dashboard_views": dashboard.active_dashboard_views,
        })
    except Exception as e:
        _LOGGER.error("HA-Modul Status fehlgeschlagen: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# -- GET /connection ---------------------------------------------------------

@ha_module_bp.route("/connection", methods=["GET"])
def get_connection():
    """Gibt den Verbindungsstatus zurueck."""
    try:
        engine = _get_engine()
        dashboard = engine.get_status()
        return jsonify({
            "status": "ok",
            **dashboard.connection,
        })
    except Exception as e:
        _LOGGER.error("HA-Modul Connection fehlgeschlagen: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# -- GET /events -------------------------------------------------------------

@ha_module_bp.route("/events", methods=["GET"])
def get_events():
    """Gibt Event-Forwarding-Statistiken zurueck."""
    try:
        engine = _get_engine()
        dashboard = engine.get_status()
        return jsonify({
            "status": "ok",
            **dashboard.event_forwarding,
        })
    except Exception as e:
        _LOGGER.error("HA-Modul Events fehlgeschlagen: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# -- POST /events/config ----------------------------------------------------

@ha_module_bp.route("/events/config", methods=["POST"])
def configure_events():
    """Konfiguriert die weitergeleiteten Domains.

    Body: {"domains": ["light", "switch", "climate", ...]}
    """
    try:
        data = request.get_json(silent=True)
        if not data or not isinstance(data.get("domains"), list):
            return jsonify({
                "status": "error",
                "message": "Missing or invalid 'domains' list in request body",
            }), 400

        domains = [str(d) for d in data["domains"] if isinstance(d, str)]
        if not domains:
            return jsonify({
                "status": "error",
                "message": "At least one domain string required",
            }), 400

        engine = _get_engine()
        engine.configure_forwarded_domains(domains)

        return jsonify({
            "status": "ok",
            "message": f"Event forwarding configured for {len(domains)} domains",
            "domains": domains,
        })
    except Exception as e:
        _LOGGER.error("HA-Modul Events Config fehlgeschlagen: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500
