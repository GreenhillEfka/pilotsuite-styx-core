from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
casdoor_bp = Blueprint("casdoor", __name__, url_prefix="/api/v1/casdoor")
@casdoor_bp.route("", methods=["GET"])
@require_token
def casdoor(): return jsonify({"ok": True})
