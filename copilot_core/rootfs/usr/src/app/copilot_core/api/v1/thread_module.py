"""Thread Network Module API — status and device listing.

Proxies to the hub_thread service for Thread mesh network health,
device inventory, and border router status.

Blueprint prefix: /api/v1/modules/thread
"""
from __future__ import annotations

import logging

from flask import Blueprint, jsonify, request, current_app

from copilot_core.api.security import validate_token as _validate_token

_LOGGER = logging.getLogger(__name__)

thread_module_bp = Blueprint(
    "thread_module_bp", __name__, url_prefix="/api/v1/modules/thread"
)


@thread_module_bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized"}), 401


def _get_service():
    """Return hub_thread service or (None, error-response)."""
    svc = current_app.config.get("COPILOT_SERVICES", {}).get("hub_thread")
    if svc is None:
        return None, (
            jsonify({
                "ok": False,
                "error": "Thread module not available",
                "hint": "hub_thread service is not initialized",
            }),
            503,
        )
    return svc, None


@thread_module_bp.get("/status")
def thread_status():
    """Return Thread network status and border router info."""
    svc, err = _get_service()
    if err:
        return err

    try:
        summary = svc.get_summary()
    except Exception as exc:
        _LOGGER.exception("Failed to get Thread status")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({"ok": True, "protocol": "thread", **summary})


@thread_module_bp.get("/devices")
def thread_devices():
    """Return list of known Thread devices."""
    svc, err = _get_service()
    if err:
        return err

    try:
        summary = svc.get_summary()
        devices = summary.get("devices", [])
    except Exception as exc:
        _LOGGER.exception("Failed to list Thread devices")
        return jsonify({"ok": False, "error": str(exc)}), 500

    return jsonify({
        "ok": True,
        "protocol": "thread",
        "total": len(devices),
        "devices": devices,
    })
