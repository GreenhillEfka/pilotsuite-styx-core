from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
fairplay_bp = Blueprint("fairplay", __name__, url_prefix="/api/v1/fairplay")
@fairplay_bp.route("", methods=["GET"])
@require_token
def fairplay(): return jsonify({"ok": True})
