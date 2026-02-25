from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
hls_bp = Blueprint("hls", __name__, url_prefix="/api/v1/hls")
@hls_bp.route("", methods=["GET"])
@require_token
def hls(): return jsonify({"ok": True})
