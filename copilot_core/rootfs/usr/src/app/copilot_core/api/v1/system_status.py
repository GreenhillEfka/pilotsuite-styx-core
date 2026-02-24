"""
PilotSuite System Status API - v7.12.0

Zentraler Status-Endpoint für das gesamte System.
"""

from flask import Blueprint, jsonify, request
import logging
import time

from copilot_core.api.security import require_token

logger = logging.getLogger(__name__)

system_status_bp = Blueprint("system_status", __name__, url_prefix="/api/v1/system")


def _now_iso():
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


@system_status_bp.route("/status", methods=["GET"])
@require_token
def get_status():
    """Get complete system status."""
    from flask import current_app
    
    services = current_app.config.get("COPILOT_SERVICES", {})
    
    # Collect service statuses
    service_status = {}
    for svc_name in [
        "brain_graph_service",
        "conversation_memory", 
        "vector_store",
        "habitus_service",
        "mood_service",
        "neuron_manager",
        "module_registry",
        "hub_dashboard",
    ]:
        service_status[svc_name] = services.get(svc_name) is not None
    
    return jsonify({
        "ok": True,
        "time": _now_iso(),
        "uptime_seconds": int(time.time() - current_app.config.get("STARTUP_TIME", time.time())),
        "services": service_status,
    })


@system_status_bp.route("/modules", methods=["GET"])
@require_token
def list_modules():
    """List all registered modules."""
    from flask import current_app
    
    registry = current_app.config.get("COPILOT_SERVICES", {}).get("module_registry")
    if not registry:
        return jsonify({"error": "Module registry not available"}), 503
    
    try:
        modules = registry.list_modules()
        return jsonify({
            "ok": True,
            "modules": modules,
            "count": len(modules),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@system_status_bp.route("/config", methods=["GET"])
@require_token
def get_config():
    """Get current configuration (safe fields only)."""
    from flask import current_app
    
    services = current_app.config.get("COPILOT_SERVICES", {})
    config = services.get("config", {})
    
    # Filter sensitive fields
    safe_config = {
        "version": config.get("version"),
        "conversation_enabled": config.get("conversation_enabled"),
        "searxng_enabled": config.get("searxng_enabled"),
    }
    
    return jsonify({
        "ok": True,
        "config": safe_config,
    })
