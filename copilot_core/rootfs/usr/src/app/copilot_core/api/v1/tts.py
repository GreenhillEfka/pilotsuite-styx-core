from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
tts_bp = Blueprint("tts", __name__, url_prefix="/api/v1/tts")
@tts_bp.route("", methods=["GET"])
@require_token
def tts(): return jsonify({"ok": True})
