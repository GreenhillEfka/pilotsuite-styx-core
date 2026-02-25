from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
speaker_bp = Blueprint("speaker", __name__, url_prefix="/api/v1/speaker")
@speaker_bp.route("", methods=["GET"])
@require_token
def speaker(): return jsonify({"ok": True})
