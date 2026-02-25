from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
resolution_bp = Blueprint("resolution", __name__, url_prefix="/api/v1/resolution")
@resolution_bp.route("", methods=["GET"])
@require_token
def resolution(): return jsonify({"ok": True})
