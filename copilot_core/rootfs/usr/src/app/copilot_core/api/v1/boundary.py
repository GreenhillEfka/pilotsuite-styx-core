from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
boundary_bp = Blueprint("boundary", __name__, url_prefix="/api/v1/boundary")
@boundary_bp.route("", methods=["GET"])
@require_token
def boundary(): return jsonify({"ok": True})
