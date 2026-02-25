from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
video_bp = Blueprint("video", __name__, url_prefix="/api/v1/video")
@video_bp.route("", methods=["GET"])
@require_token
def video(): return jsonify({"ok": True})
