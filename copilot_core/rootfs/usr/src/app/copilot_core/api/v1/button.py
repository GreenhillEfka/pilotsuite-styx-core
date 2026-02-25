from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
button_bp = Blueprint("button", __name__, url_prefix="/api/v1/button")
@button_bp.route("", methods=["GET"])
@require_token
def button(): return jsonify({"ok": True})
