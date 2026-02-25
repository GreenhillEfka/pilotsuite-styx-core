"""
Energy API - PilotSuite v7.31.0
"""

from flask import Blueprint, jsonify, request
from copilot_core.api.security import require_token

energy_bp = Blueprint("energy", __name__, url_prefix="/api/v1/energy")


@energy_bp.route("", methods=["GET"])
@require_token
def get_energy():
    return jsonify({"ok": True, "message": "Energy API"})


@energy_bp.route("/config", methods=["GET"])
@require_token
def get_energy_config():
    return jsonify({"ok": True, "solar": None, "grid": None})
