"""Zigbee Network Module API — status and device listing.

Proxies to the hub_zigbee service for Zigbee network health,
device inventory, and coordinator status.

Blueprint prefix: /api/v1/modules/zigbee
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request, current_app

from copilot_core.api.security import validate_token as _validate_token

_LOGGER = logging.getLogger(__name__)

zigbee_module_bp = Blueprint(
    "zigbee_module_bp", __name__, url_prefix="/api/v1/modules/zigbee"
)


@zigbee_module_bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized"}), 401


def _get_service():
    """Return hub_zigbee service or (None, error-response)."""
    svc = current_app.config.get("COPILOT_SERVICES", {}).get("hub_zigbee")
    if svc is None:
        return None, (
            jsonify({
                "ok": False,
                "error": "Zigbee module not available",
                "hint": "hub_zigbee service is not initialized",
            }),
            503,
        )
    return svc, None


@zigbee_module_bp.get("/status")
def zigbee_status():
    """Return Zigbee network status and coordinator info."""
    svc, err = _get_service()
    if err:
        return err

    try:
        summary = svc.get_summary()
    except Exception as exc:
        _LOGGER.exception("Failed to get Zigbee status")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "protocol": "zigbee", **summary})


@zigbee_module_bp.get("/devices")
def zigbee_devices():
    """Return list of known Zigbee devices."""
    svc, err = _get_service()
    if err:
        return err

    try:
        summary = svc.get_summary()
        devices = summary.get("devices", [])
    except Exception as exc:
        _LOGGER.exception("Failed to list Zigbee devices")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({
        "ok": True,
        "protocol": "zigbee",
        "total": len(devices),
        "devices": devices,
    })


@zigbee_module_bp.get("/config")
def zigbee_config():
    """Return Zigbee module configuration."""
    svc, err = _get_service()
    if err:
        return err

    try:
        config = svc.get_config()
    except Exception as exc:
        _LOGGER.exception("Failed to get Zigbee config")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "protocol": "zigbee", "config": config})


@zigbee_module_bp.post("/config")
def zigbee_update_config():
    """Update Zigbee module configuration."""
    svc, err = _get_service()
    if err:
        return err

    data = request.get_json(silent=True) or {}
    try:
        updated = svc.update_config(data)
        router = current_app.config.get("COPILOT_SERVICES", {}).get("module_router")
        if router:
            router.update_config("zigbee", updated)
    except Exception as exc:
        _LOGGER.exception("Failed to update Zigbee config")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "protocol": "zigbee", "config": updated})


@zigbee_module_bp.post("/refresh")
def zigbee_refresh():
    """Trigger immediate Zigbee state refresh from HA."""
    import asyncio

    router = current_app.config.get("COPILOT_SERVICES", {}).get("module_router")
    if not router:
        return jsonify({"ok": False, "error": "ModuleRouter not available"}), 503

    try:
        result = asyncio.run(router.async_refresh_from_ha())
    except Exception as exc:
        _LOGGER.exception("Failed to refresh Zigbee")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "protocol": "zigbee", **result})
