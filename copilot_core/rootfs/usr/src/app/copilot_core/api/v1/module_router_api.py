"""Module Router API — Netzwerk-Modul-Uebersicht und Refresh.

Zentraler Endpoint fuer den ModuleRouter: Status aller Netzwerk-Module,
globale Konfiguration, und manuelles Refresh.

Blueprint prefix: /api/v1/modules/router
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request, current_app

from copilot_core.api.security import validate_token as _validate_token

_LOGGER = logging.getLogger(__name__)

module_router_bp = Blueprint(
    "module_router_bp", __name__, url_prefix="/api/v1/modules/router"
)


@module_router_bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized"}), 401


def _get_router():
    """Return module_router service or (None, error-response)."""
    svc = current_app.config.get("COPILOT_SERVICES", {}).get("module_router")
    if svc is None:
        return None, (
            jsonify({
                "ok": False,
                "error": "ModuleRouter not available",
                "hint": "module_router service is not initialized",
            }),
            503,
        )
    return svc, None


@module_router_bp.get("/status")
def router_status():
    """Return status of all network modules via ModuleRouter."""
    router, err = _get_router()
    if err:
        return err

    try:
        status = router.get_status()
    except Exception as exc:
        _LOGGER.exception("Failed to get ModuleRouter status")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, **status})


@module_router_bp.get("/config")
def router_config():
    """Return configuration of all network modules."""
    router, err = _get_router()
    if err:
        return err

    try:
        config = router.get_config()
    except Exception as exc:
        _LOGGER.exception("Failed to get ModuleRouter config")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "config": config})


@module_router_bp.post("/config/<module>")
def router_update_config(module: str):
    """Update configuration of a specific network module.

    URL: /api/v1/modules/router/config/zwave
    Body: {"polling_interval_s": 60, "alert_dead_devices": false}
    """
    router, err = _get_router()
    if err:
        return err

    valid_modules = ("zwave", "zigbee", "thread", "homeassistant")
    if module not in valid_modules:
        return jsonify({
            "ok": False,
            "error": f"Unknown module '{module}'",
            "valid": list(valid_modules),
        }), 400

    data = request.get_json(silent=True) or {}
    try:
        updated = router.update_config(module, data)
    except Exception as exc:
        _LOGGER.exception("Failed to update config for %s", module)
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "module": module, "config": updated})


@module_router_bp.post("/refresh")
def router_refresh():
    """Trigger immediate refresh of all network modules from HA.

    Uses HomeAssistantClient.get_states() to fetch all entity states
    and routes them to the network module engines.
    """
    import asyncio

    router, err = _get_router()
    if err:
        return err

    try:
        # Try to use existing event loop, fall back to asyncio.run
        try:
            loop = asyncio.get_running_loop()
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(
                router.async_refresh_from_ha(), loop
            )
            result = future.result(timeout=30)
        except RuntimeError:
            result = asyncio.run(router.async_refresh_from_ha())
    except Exception as exc:
        _LOGGER.exception("Failed to refresh network modules")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, **result})
