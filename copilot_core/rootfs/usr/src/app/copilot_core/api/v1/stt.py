from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
stt_bp = Blueprint("stt", __name__, url_prefix="/api/v1/stt")
@stt_bp.route("", methods=["GET"])
@require_token
def stt(): return jsonify({"ok": True})
