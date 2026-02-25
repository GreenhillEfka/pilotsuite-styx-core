from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
dns_bp = Blueprint("dns", __name__, url_prefix="/api/v1/dns")
@dns_bp.route("", methods=["GET"])
@require_token
def dns(): return jsonify({"ok": True})
