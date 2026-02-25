from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ratelimit_bp = Blueprint("ratelimit", __name__, url_prefix="/api/v1/ratelimit")
@ratelimit_bp.route("", methods=["GET"])
@require_token
def ratelimit(): return jsonify({"ok": True})
