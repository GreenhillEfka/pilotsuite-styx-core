from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
textgenwebui_bp = Blueprint("textgenwebui", __name__, url_prefix="/api/v1/textgenwebui")
@textgenwebui_bp.route("", methods=["GET"])
@require_token
def textgenwebui(): return jsonify({"ok": True})
