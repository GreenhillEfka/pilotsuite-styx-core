from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
gateway_bp = Blueprint("gateway", __name__, url_prefix="/api/v1/gateway")
@gateway_bp.route("", methods=["GET"])
@require_token
def gateway(): return jsonify({"ok": True})
