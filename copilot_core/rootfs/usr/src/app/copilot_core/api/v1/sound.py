from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
sound_bp = Blueprint("sound", __name__, url_prefix="/api/v1/sound")
@sound_bp.route("", methods=["GET"])
@require_token
def sound(): return jsonify({"ok": True})
