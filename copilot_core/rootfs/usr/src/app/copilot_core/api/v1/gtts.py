from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
gtts_bp = Blueprint("gtts", __name__, url_prefix="/api/v1/gtts")
@gtts_bp.route("", methods=["GET"])
@require_token
def gtts(): return jsonify({"ok": True})
