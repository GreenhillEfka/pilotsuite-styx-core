from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
wifip2p_bp = Blueprint("wifip2p", __name__, url_prefix="/api/v1/wifip2p")
@wifip2p_bp.route("", methods=["GET"])
@require_token
def wifip2p(): return jsonify({"ok": True})
