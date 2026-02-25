"""
Core API - PilotSuite v7.43
"""

from flask import Blueprint, jsonify
from copilot_core.api.security import require_token

core_bp = Blueprint("core", __name__, url_prefix="/api/v1/core")

@core_bp.route("", methods=["GET"])
@require_token
def core_info():
    return jsonify({"ok": True, "version": "2024.1.0"})
