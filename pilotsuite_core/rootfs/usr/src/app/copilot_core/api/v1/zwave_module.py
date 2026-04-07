"""Z-Wave Network Module API — status and device listing.

Proxies to the hub_zwave service for Z-Wave network health,
device inventory, and controller status.

Blueprint prefix: /api/v1/modules/zwave
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request, current_app

from copilot_core.api.security import validate_token as _validate_token

_LOGGER = logging.getLogger(__name__)

zwave_module_bp = Blueprint(
    "zwave_module_bp", __name__, url_prefix="/api/v1/modules/zwave"
)


@zwave_module_bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized"}), 401


def _get_service():
    """Return hub_zwave service or (None, error-response)."""
    svc = current_app.config.get("COPILOT_SERVICES", {}).get("hub_zwave")
    if svc is None:
        return None, (
            jsonify({
                "ok": False,
                "error": "Z-Wave module not available",
                "hint": "hub_zwave service is not initialized",
            }),
            503,
        )
    return svc, None


@zwave_module_bp.get("/status")
def zwave_status():
    """Return Z-Wave network status and controller info."""
    svc, err = _get_service()
    if err:
        return err

    try:
        summary = svc.get_summary()
    except Exception as exc:
        _LOGGER.exception("Failed to get Z-Wave status")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "protocol": "zwave", **summary})


@zwave_module_bp.get("/devices")
def zwave_devices():
    """Return list of known Z-Wave devices."""
    svc, err = _get_service()
    if err:
        return err

    try:
        summary = svc.get_summary()
        devices = summary.get("devices", [])
    except Exception as exc:
        _LOGGER.exception("Failed to list Z-Wave devices")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({
        "ok": True,
        "protocol": "zwave",
        "total": len(devices),
        "devices": devices,
    })


@zwave_module_bp.get("/config")
def zwave_config():
    """Return Z-Wave module configuration."""
    svc, err = _get_service()
    if err:
        return err

    try:
        config = svc.get_config()
    except Exception as exc:
        _LOGGER.exception("Failed to get Z-Wave config")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "protocol": "zwave", "config": config})


@zwave_module_bp.post("/config")
def zwave_update_config():
    """Update Z-Wave module configuration."""
    svc, err = _get_service()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    try:
        updated = svc.update_config(data)
        # Persist via ModuleRouter if available
        router = current_app.config.get("COPILOT_SERVICES", {}).get("module_router")
        if router:
            router.update_config("zwave", updated)
    except Exception as exc:
        _LOGGER.exception("Failed to update Z-Wave config")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "protocol": "zwave", "config": updated})


@zwave_module_bp.post("/refresh")
def zwave_refresh():
    """Trigger immediate Z-Wave state refresh from HA."""
    import asyncio

    router = current_app.config.get("COPILOT_SERVICES", {}).get("module_router")
    if not router:
        return jsonify({"ok": False, "error": "ModuleRouter not available"}), 503

    try:
        result = asyncio.run(router.async_refresh_from_ha())
    except Exception as exc:
        _LOGGER.exception("Failed to refresh Z-Wave")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "protocol": "zwave", **result})
