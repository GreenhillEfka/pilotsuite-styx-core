from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
redis_bp = Blueprint("redis", __name__, url_prefix="/api/v1/redis")
@redis_bp.route("", methods=["GET"])
@require_token
def redis(): return jsonify({"ok": True})
