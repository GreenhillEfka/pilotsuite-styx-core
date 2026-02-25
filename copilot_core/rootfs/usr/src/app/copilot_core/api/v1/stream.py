from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
stream_bp = Blueprint("stream", __name__, url_prefix="/api/v1/stream")
@stream_bp.route("", methods=["GET"])
@require_token
def stream(): return jsonify({"ok": True})
