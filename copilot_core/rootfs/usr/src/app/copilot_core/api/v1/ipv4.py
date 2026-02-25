from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ipv4_bp = Blueprint("ipv4", __name__, url_prefix="/api/v1/ipv4")
@ipv4_bp.route("", methods=["GET"])
@require_token
def ipv4(): return jsonify({"ok": True})
