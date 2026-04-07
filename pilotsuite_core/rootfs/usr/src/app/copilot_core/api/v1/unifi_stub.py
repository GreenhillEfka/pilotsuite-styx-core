"""UniFi API stub — returns empty/placeholder data.

HA sensors (tariff, weather_warning, battery_optimizer, etc.) call
/api/v1/unifi, /api/v1/unifi/wan, /api/v1/unifi/clients, /api/v1/unifi/roaming.
Without this stub they get 404 and log errors every polling cycle.
"""
from flask import Blueprint, jsonify, request

from copilot_core.api.security import validate_token as _validate_token

unifi_stub_bp = Blueprint("unifi_stub", __name__, url_prefix="/api/v1/unifi")


@unifi_stub_bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized"}), 401


@unifi_stub_bp.get("/")
def unifi_root():
    """UniFi overview — stub."""
    return jsonify({
        "ok": True,
        "status": "not_configured",
        "message": "UniFi integration not configured in Core Add-on",
        "devices": [],
        "clients": [],
    })


@unifi_stub_bp.get("/wan")
def unifi_wan():
    """WAN status — stub."""
    return jsonify({
        "ok": True,
        "status": "not_configured",
        "wan": {},
    })


@unifi_stub_bp.get("/clients")
def unifi_clients():
    """Client list — stub."""
    return jsonify({
        "ok": True,
        "status": "not_configured",
        "clients": [],
    })


@unifi_stub_bp.get("/roaming")
def unifi_roaming():
    """Roaming status — stub."""
    return jsonify({
        "ok": True,
        "status": "not_configured",
        "roaming_events": [],
    })
