from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
localai_bp = Blueprint("localai", __name__, url_prefix="/api/v1/localai")
@localai_bp.route("", methods=["GET"])
@require_token
def localai(): return jsonify({"ok": True})
