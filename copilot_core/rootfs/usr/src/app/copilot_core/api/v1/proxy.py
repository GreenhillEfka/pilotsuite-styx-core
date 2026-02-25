from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
proxy_bp = Blueprint("proxy", __name__, url_prefix="/api/v1/proxy")
@proxy_bp.route("", methods=["GET"])
@require_token
def proxy(): return jsonify({"ok": True})
