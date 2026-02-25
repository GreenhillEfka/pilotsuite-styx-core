"""
Network API - PilotSuite v7.42
"""

from flask import Blueprint, jsonify
from copilot_core.api.security import require_token

network_bp = Blueprint("network", __name__, url_prefix="/api/v1/network")

@network_bp.route("", methods=["GET"])
@require_token
def network_status():
    return jsonify({"ok": True, "hosts": []})
