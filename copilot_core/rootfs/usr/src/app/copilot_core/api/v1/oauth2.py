from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
oauth2_bp = Blueprint("oauth2", __name__, url_prefix="/api/v1/oauth2")
@oauth2_bp.route("", methods=["GET"])
@require_token
def oauth2(): return jsonify({"ok": True})
