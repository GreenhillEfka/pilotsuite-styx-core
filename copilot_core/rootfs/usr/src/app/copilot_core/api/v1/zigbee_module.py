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
