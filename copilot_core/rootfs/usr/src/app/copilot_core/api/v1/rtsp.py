from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
rtsp_bp = Blueprint("rtsp", __name__, url_prefix="/api/v1/rtsp")
@rtsp_bp.route("", methods=["GET"])
@require_token
def rtsp(): return jsonify({"ok": True})
