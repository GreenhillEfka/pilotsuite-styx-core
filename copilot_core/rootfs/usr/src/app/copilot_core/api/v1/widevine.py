from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
widevine_bp = Blueprint("widevine", __name__, url_prefix="/api/v1/widevine")
@widevine_bp.route("", methods=["GET"])
@require_token
def widevine(): return jsonify({"ok": True})
