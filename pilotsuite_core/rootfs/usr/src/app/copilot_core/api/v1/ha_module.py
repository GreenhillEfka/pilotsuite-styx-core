"""HomeAssistant Integration Module API — Status, Diagnostik und Konfiguration."""

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


def _json_error(message: str, status_code: int = 400):
    return jsonify({"status": "error", "message": message}), status_code


def _require_json_object(*, allow_missing: bool = False) -> tuple[dict, tuple | None]:
    data = request.get_json(silent=True)
    if data is None:
        if allow_missing:
            return {}, None
        return {}, _json_error("Request body required")
    if not isinstance(data, dict):
        return {}, _json_error("JSON body must be an object")
    return data, None


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
        if data is None:
            return jsonify({
                "status": "error",
                "message": "Missing or invalid 'domains' list in request body",
            }), 400
        if not isinstance(data, dict):
            return _json_error("JSON body must be an object")
        if not isinstance(data.get("domains"), list):
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


# -- GET /config ----------------------------------------------------------------

@ha_module_bp.route("/config", methods=["GET"])
def get_config():
    """Gibt die vollstaendige Modul-Konfiguration zurueck."""
    try:
        engine = _get_engine()
        config = engine.get_config()
        return jsonify({"status": "ok", "module": "homeassistant", "config": config})
    except Exception as e:
        _LOGGER.error("HA-Modul Config Lesen fehlgeschlagen: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# -- POST /config ---------------------------------------------------------------

@ha_module_bp.route("/config", methods=["POST"])
def update_config():
    """Aktualisiert die Modul-Konfiguration.

    Body: {"forwarded_domains": [...], "webhook_retry_count": 3, ...}
    """
    try:
        data, error = _require_json_object()
        if error:
            return error

        engine = _get_engine()
        updated = engine.update_config(data)

        # Persist via ModuleRouter if available
        router = current_app.config.get("COPILOT_SERVICES", {}).get("module_router")
        if router:
            router.update_config("homeassistant", updated)

        return jsonify({"status": "ok", "module": "homeassistant", "config": updated})
    except Exception as e:
        _LOGGER.error("HA-Modul Config Update fehlgeschlagen: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# -- GET /diagnostics -----------------------------------------------------------

@ha_module_bp.route("/diagnostics", methods=["GET"])
def get_diagnostics():
    """Gibt vollstaendige Diagnostik-Informationen zurueck.

    Umfasst Connection-Diagnostics, bidirektionale Webhook-Metriken,
    Pipeline-Health, Event-Forwarding-Details und Konfiguration.
    """
    try:
        engine = _get_engine()
        diag = engine.get_diagnostics()
        health = engine.get_pipeline_health()
        return jsonify({
            "status": "ok",
            "module": "homeassistant",
            "diagnostics": diag,
            "pipeline_health": health,
        })
    except Exception as e:
        _LOGGER.error("HA-Modul Diagnostics fehlgeschlagen: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# -- GET /health ----------------------------------------------------------------

@ha_module_bp.route("/health", methods=["GET"])
def get_health():
    """Gibt Pipeline-Health-Summary mit Status-Farben zurueck."""
    try:
        engine = _get_engine()
        health = engine.get_pipeline_health()
        return jsonify({
            "status": "ok",
            "module": "homeassistant",
            **health,
        })
    except Exception as e:
        _LOGGER.error("HA-Modul Health fehlgeschlagen: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# -- POST /webhook-received ----------------------------------------------------

@ha_module_bp.route("/webhook-received", methods=["POST"])
def webhook_received():
    """Zeichnet einen empfangenen Webhook (HA -> Core) auf.

    Wird von der HA-Integration aufgerufen um den Empfang zu quittieren.

    Body: {"event_type": "state_changed"}
    Optionale Felder: {"event_type": "...", "count": 5}
    """
    try:
        data, error = _require_json_object(allow_missing=True)
        if error:
            return error

        event_type = data.get("event_type", "unknown")
        if not isinstance(event_type, str) or not event_type.strip():
            event_type = "unknown"

        engine = _get_engine()
        engine.record_webhook(event_type.strip())

        return jsonify({
            "status": "ok",
            "message": f"Webhook recorded: {event_type}",
            "webhook_received_count": engine._webhook_received_count,
        })
    except Exception as e:
        _LOGGER.error("HA-Modul Webhook-Received fehlgeschlagen: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500


# -- POST /refresh --------------------------------------------------------------

@ha_module_bp.route("/refresh", methods=["POST"])
def refresh():
    """Triggert sofortiges Refresh aller Netzwerk-Module aus HA."""
    import asyncio

    router = current_app.config.get("COPILOT_SERVICES", {}).get("module_router")
    if not router:
        return jsonify({"status": "error", "message": "ModuleRouter not available"}), 503

    try:
        result = asyncio.run(router.async_refresh_from_ha())
    except Exception as e:
        _LOGGER.error("HA-Modul Refresh fehlgeschlagen: %s", e)
        return jsonify({"status": "error", "message": str(e)}), 500

    return jsonify({"status": "ok", "module": "homeassistant", **result})
