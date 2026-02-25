"""
Helpers API - PilotSuite v7.37
"""

from flask import Blueprint, jsonify
from copilot_core.api.security import require_token

helpers_bp = Blueprint("helpers", __name__, url_prefix="/api/v1/helpers")

@helpers_bp.route("", methods=["GET"])
@require_token
def list_helpers():
    return jsonify({"ok": True, "helpers": []})
