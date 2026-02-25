from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
srt_bp = Blueprint("srt", __name__, url_prefix="/api/v1/srt")
@srt_bp.route("", methods=["GET"])
@require_token
def srt(): return jsonify({"ok": True})
