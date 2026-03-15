"""Comfort API stub — returns placeholder data.

HA sensors call /api/v1/comfort and /api/v1/comfort/lighting.
"""
from flask import Blueprint, jsonify, request

from copilot_core.api.security import validate_token as _validate_token

comfort_stub_bp = Blueprint("comfort_stub", __name__, url_prefix="/api/v1/comfort")


@comfort_stub_bp.before_request
def _require_auth():
    if not _validate_token(request):
        return jsonify({"error": "unauthorized"}), 401


@comfort_stub_bp.get("/")
def comfort_root():
    """Comfort index — stub."""
    return jsonify({
        "ok": True,
        "status": "not_configured",
        "comfort_index": 0.7,
        "factors": {},
    })


@comfort_stub_bp.get("/lighting")
def comfort_lighting():
    """Comfort lighting — stub."""
    return jsonify({
        "ok": True,
        "status": "not_configured",
        "lighting": {},
    })
