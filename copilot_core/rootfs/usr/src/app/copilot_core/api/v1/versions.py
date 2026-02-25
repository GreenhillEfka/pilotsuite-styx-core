"""
Versions API - PilotSuite v7.36
"""

from flask import Blueprint, jsonify
from copilot_core.api.security import require_token

versions_bp = Blueprint("versions", __name__, url_prefix="/api/v1/versions")

@versions_bp.route("", methods=["GET"])
@require_token
def get_versions():
    return jsonify({
        "ok": True,
        "versions": {
            "core": "7.35.0",
            "addon": "7.35.0",
            "api": "v1"
        }
    })
