from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ws_bp = Blueprint("ws", __name__, url_prefix="/api/v1/ws")
@ws_bp.route("", methods=["GET"])
@require_token
def ws(): return jsonify({"ok": True})
