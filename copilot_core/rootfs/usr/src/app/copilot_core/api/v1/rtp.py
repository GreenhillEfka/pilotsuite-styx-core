from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
rtp_bp = Blueprint("rtp", __name__, url_prefix="/api/v1/rtp")
@rtp_bp.route("", methods=["GET"])
@require_token
def rtp(): return jsonify({"ok": True})
