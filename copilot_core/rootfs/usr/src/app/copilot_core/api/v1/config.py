"""Lightweight runtime config inspection API.

This surface intentionally exposes only non-secret summary data so the registry
contains a real Flask blueprint without leaking credentials.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify, request

from copilot_core.api.security import validate_token
from copilot_core.versioning import get_runtime_version

config_bp = Blueprint("config", __name__, url_prefix="/api/v1/config")

_PUBLIC_CONFIG_KEYS = (
    "DEBUG",
    "TESTING",
    "ENV",
    "APPLICATION_ROOT",
    "PREFERRED_URL_SCHEME",
)


@config_bp.before_request
def _require_auth():
    if not validate_token(request):
        return jsonify({"ok": False, "error": "unauthorized"}), 401


@config_bp.get("")
def get_config_summary():
    app_config = current_app.config
    services = app_config.get("COPILOT_SERVICES", {}) or {}

    return jsonify(
        {
            "ok": True,
            "version": get_runtime_version(),
            "config": {key: app_config.get(key) for key in _PUBLIC_CONFIG_KEYS if key in app_config},
            "service_count": len(services),
            "service_keys": sorted(str(key) for key in services.keys()),
        }
    )


@config_bp.get("/services")
def get_config_services():
    services = current_app.config.get("COPILOT_SERVICES", {}) or {}
    return jsonify(
        {
            "ok": True,
            "count": len(services),
            "services": sorted(str(key) for key in services.keys()),
        }
    )


__all__ = ["config_bp"]
