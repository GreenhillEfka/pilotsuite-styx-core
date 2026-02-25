"""
Logbook API v2 - PilotSuite v7.47
"""

from flask import Blueprint, jsonify
from copilot_core.api.security import require_token

logbook2_bp = Blueprint("logbook2", __name__, url_prefix="/api/v1/logbook2")

@logbook2_bp.route("", methods=["GET"])
@require_token
def logbook2():
    return jsonify({"ok": True})
