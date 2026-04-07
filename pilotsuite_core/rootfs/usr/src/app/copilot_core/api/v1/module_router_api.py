"""Module Router API — Netzwerk-Modul-Uebersicht und Refresh.
module_router_bp = bp

module_router_bp = bp
Zentraler Endpoint fuer den ModuleRouter: Status aller Netzwerk-Module,
module_router_bp = bp
globale Konfiguration, und manuelles Refresh.
module_router_bp = bp

module_router_bp = bp
Blueprint prefix: /api/v1/modules/router
module_router_bp = bp
"""
module_router_bp = bp
from __future__ import annotations
module_router_bp = bp

module_router_bp = bp
import logging
module_router_bp = bp

module_router_bp = bp
from flask import Blueprint, jsonify, request, current_app
module_router_bp = bp

module_router_bp = bp
from copilot_core.api.security import validate_token as _validate_token
module_router_bp = bp

module_router_bp = bp
_LOGGER = logging.getLogger(__name__)
module_router_bp = bp

module_router_bp = bp
module_router_bp = Blueprint(
module_router_bp = bp
    "module_router_bp", __name__, url_prefix="/api/v1/modules/router"
module_router_bp = bp
)
module_router_bp = bp

module_router_bp = bp

module_router_bp = bp
@module_router_bp.before_request
module_router_bp = bp
def _require_auth():
module_router_bp = bp
    if not _validate_token(request):
module_router_bp = bp
        return jsonify({"error": "unauthorized"}), 401
module_router_bp = bp

module_router_bp = bp

module_router_bp = bp
def _get_router():
module_router_bp = bp
    """Return module_router service or (None, error-response)."""
module_router_bp = bp
    svc = current_app.config.get("COPILOT_SERVICES", {}).get("module_router")
module_router_bp = bp
    if svc is None:
module_router_bp = bp
        return None, (
module_router_bp = bp
            jsonify({
module_router_bp = bp
                "ok": False,
module_router_bp = bp
                "error": "ModuleRouter not available",
module_router_bp = bp
                "hint": "module_router service is not initialized",
module_router_bp = bp
            }),
module_router_bp = bp
            503,
module_router_bp = bp
        )
module_router_bp = bp
    return svc, None
module_router_bp = bp

module_router_bp = bp

module_router_bp = bp
@module_router_bp.get("/status")
module_router_bp = bp
def router_status():
module_router_bp = bp
    """Return status of all network modules via ModuleRouter."""
module_router_bp = bp
    router, err = _get_router()
module_router_bp = bp
    if err:
module_router_bp = bp
        return err
module_router_bp = bp

module_router_bp = bp
    try:
module_router_bp = bp
        status = router.get_status()
module_router_bp = bp
    except Exception as exc:
module_router_bp = bp
        _LOGGER.exception("Failed to get ModuleRouter status")
module_router_bp = bp
        return jsonify({"ok": False, "error": str(exc)}), 500
module_router_bp = bp

module_router_bp = bp
    return jsonify({"ok": True, **status})
module_router_bp = bp

module_router_bp = bp

module_router_bp = bp
@module_router_bp.get("/config")
module_router_bp = bp
def router_config():
module_router_bp = bp
    """Return configuration of all network modules."""
module_router_bp = bp
    router, err = _get_router()
module_router_bp = bp
    if err:
module_router_bp = bp
        return err
module_router_bp = bp

module_router_bp = bp
    try:
module_router_bp = bp
        config = router.get_config()
module_router_bp = bp
    except Exception as exc:
module_router_bp = bp
        _LOGGER.exception("Failed to get ModuleRouter config")
module_router_bp = bp
        return jsonify({"ok": False, "error": str(exc)}), 500
module_router_bp = bp

module_router_bp = bp
    return jsonify({"ok": True, "config": config})
module_router_bp = bp

module_router_bp = bp

module_router_bp = bp
@module_router_bp.post("/config/<module>")
module_router_bp = bp
def router_update_config(module: str):
module_router_bp = bp
    """Update configuration of a specific network module.
module_router_bp = bp

module_router_bp = bp
    URL: /api/v1/modules/router/config/zwave
module_router_bp = bp
    Body: {"polling_interval_s": 60, "alert_dead_devices": false}
module_router_bp = bp
    """
module_router_bp = bp
    router, err = _get_router()
module_router_bp = bp
    if err:
module_router_bp = bp
        return err
module_router_bp = bp

module_router_bp = bp
    valid_modules = ("zwave", "zigbee", "thread", "homeassistant")
module_router_bp = bp
    if module not in valid_modules:
module_router_bp = bp
        return jsonify({
module_router_bp = bp
            "ok": False,
module_router_bp = bp
            "error": f"Unknown module '{module}'",
module_router_bp = bp
            "valid": list(valid_modules),
module_router_bp = bp
        }), 400
module_router_bp = bp

module_router_bp = bp
    data = request.get_json(silent=True) or {}
module_router_bp = bp
    try:
module_router_bp = bp
        updated = router.update_config(module, data)
module_router_bp = bp
    except Exception as exc:
module_router_bp = bp
        _LOGGER.exception("Failed to update config for %s", module)
module_router_bp = bp
        return jsonify({"ok": False, "error": str(exc)}), 500
module_router_bp = bp

module_router_bp = bp
    return jsonify({"ok": True, "module": module, "config": updated})
module_router_bp = bp

module_router_bp = bp

module_router_bp = bp
@module_router_bp.post("/refresh")
module_router_bp = bp
def router_refresh():
module_router_bp = bp
    """Trigger immediate refresh of all network modules from HA.
module_router_bp = bp

module_router_bp = bp
    Uses HomeAssistantClient.get_states() to fetch all entity states
module_router_bp = bp
    and routes them to the network module engines.
module_router_bp = bp
    """
module_router_bp = bp
    import asyncio
module_router_bp = bp

module_router_bp = bp
    router, err = _get_router()
module_router_bp = bp
    if err:
module_router_bp = bp
        return err
module_router_bp = bp

module_router_bp = bp
    try:
module_router_bp = bp
        # Try to use existing event loop, fall back to asyncio.run
module_router_bp = bp
        try:
module_router_bp = bp
            loop = asyncio.get_running_loop()
module_router_bp = bp
            import concurrent.futures
module_router_bp = bp
            future = asyncio.run_coroutine_threadsafe(
module_router_bp = bp
                router.async_refresh_from_ha(), loop
module_router_bp = bp
            )
module_router_bp = bp
            result = future.result(timeout=30)
module_router_bp = bp
        except RuntimeError:
module_router_bp = bp
            result = asyncio.run(router.async_refresh_from_ha())
module_router_bp = bp
    except Exception as exc:
module_router_bp = bp
        _LOGGER.exception("Failed to refresh network modules")
module_router_bp = bp
        return jsonify({"ok": False, "error": str(exc)}), 500
module_router_bp = bp

module_router_bp = bp
    return jsonify({"ok": True, **result})
module_router_bp = bp
