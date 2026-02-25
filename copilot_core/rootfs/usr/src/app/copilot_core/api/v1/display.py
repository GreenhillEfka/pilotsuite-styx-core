from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
display_bp = Blueprint("display", __name__, url_prefix="/api/v1/display")
@display_bp.route("", methods=["GET"])
@require_token
def display(): return jsonify({"ok": True})
