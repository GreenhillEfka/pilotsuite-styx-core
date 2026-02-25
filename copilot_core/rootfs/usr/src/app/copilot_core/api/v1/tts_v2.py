from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
tts2_bp = Blueprint("tts2", __name__, url_prefix="/api/v1/tts_v2")
@tts2_bp.route("", methods=["GET"])
@require_token
def tts2(): return jsonify({"ok": True})
