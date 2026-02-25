from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
hls2_bp = Blueprint("hls2", __name__, url_prefix="/api/v1/hls2")
@hls2_bp.route("", methods=["GET"])
@require_token
def hls2(): return jsonify({"ok": True})
