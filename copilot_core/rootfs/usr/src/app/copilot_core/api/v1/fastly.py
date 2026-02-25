from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
fastly_bp = Blueprint("fastly", __name__, url_prefix="/api/v1/fastly")
@fastly_bp.route("", methods=["GET"])
@require_token
def fastly(): return jsonify({"ok": True})
