from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
cache_bp = Blueprint("cache", __name__, url_prefix="/api/v1/cache")
@cache_bp.route("", methods=["GET"])
@require_token
def cache(): return jsonify({"ok": True})
