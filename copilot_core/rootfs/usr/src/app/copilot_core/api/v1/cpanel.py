from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
cpanel_bp = Blueprint("cpanel", __name__, url_prefix="/api/v1/cpanel")
@cpanel_bp.route("", methods=["GET"])
@require_token
def cpanel(): return jsonify({"ok": True})
