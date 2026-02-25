from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
mac_bp = Blueprint("mac", __name__, url_prefix="/api/v1/mac")
@mac_bp.route("", methods=["GET"])
@require_token
def mac(): return jsonify({"ok": True})
