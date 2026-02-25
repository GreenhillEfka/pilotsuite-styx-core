from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
consul_bp = Blueprint("consul", __name__, url_prefix="/api/v1/consul")
@consul_bp.route("", methods=["GET"])
@require_token
def consul(): return jsonify({"ok": True})
