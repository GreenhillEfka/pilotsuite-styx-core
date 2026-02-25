from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
memcached_bp = Blueprint("memcached", __name__, url_prefix="/api/v1/memcached")
@memcached_bp.route("", methods=["GET"])
@require_token
def memcached(): return jsonify({"ok": True})
