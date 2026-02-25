from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
webrtc_bp = Blueprint("webrtc", __name__, url_prefix="/api/v1/webrtc")
@webrtc_bp.route("", methods=["GET"])
@require_token
def webrtc(): return jsonify({"ok": True})
