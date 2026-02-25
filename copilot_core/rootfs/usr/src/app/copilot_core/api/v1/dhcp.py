from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
dhcp_bp = Blueprint("dhcp", __name__, url_prefix="/api/v1/dhcp")
@dhcp_bp.route("", methods=["GET"])
@require_token
def dhcp(): return jsonify({"ok": True})
