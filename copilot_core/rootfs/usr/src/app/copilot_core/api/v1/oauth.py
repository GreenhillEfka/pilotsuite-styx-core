"""
OAuth API - PilotSuite v7.38
"""

from flask import Blueprint, jsonify
from copilot_core.api.security import require_token

oauth_bp = Blueprint("oauth", __name__, url_prefix="/api/v1/oauth")

@oauth_bp.route("", methods=["GET"])
@require_token
def oauth_status():
    return jsonify({"ok": True, "oauth": "not_configured"})
