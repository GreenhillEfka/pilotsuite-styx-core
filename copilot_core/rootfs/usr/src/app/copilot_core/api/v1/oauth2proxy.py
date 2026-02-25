from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
oauth2proxy_bp = Blueprint("oauth2proxy", __name__, url_prefix="/api/v1/oauth2proxy")
@oauth2proxy_bp.route("", methods=["GET"])
@require_token
def oauth2proxy(): return jsonify({"ok": True})
