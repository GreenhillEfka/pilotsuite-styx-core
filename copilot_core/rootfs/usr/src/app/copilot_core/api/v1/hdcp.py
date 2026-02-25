from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
hdcp_bp = Blueprint("hdcp", __name__, url_prefix="/api/v1/hdcp")
@hdcp_bp.route("", methods=["GET"])
@require_token
def hdcp(): return jsonify({"ok": True})
