from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ipv6_bp = Blueprint("ipv6", __name__, url_prefix="/api/v1/ipv6")
@ipv6_bp.route("", methods=["GET"])
@require_token
def ipv6(): return jsonify({"ok": True})
