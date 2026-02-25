from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
audio_bp = Blueprint("audio", __name__, url_prefix="/api/v1/audio")
@audio_bp.route("", methods=["GET"])
@require_token
def audio(): return jsonify({"ok": True})
