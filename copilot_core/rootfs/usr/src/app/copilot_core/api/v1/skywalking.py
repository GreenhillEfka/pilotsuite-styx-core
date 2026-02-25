from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
skywalking_bp = Blueprint("skywalking", __name__, url_prefix="/api/v1/skywalking")
@skywalking_bp.route("", methods=["GET"])
@require_token
def skywalking(): return jsonify({"ok": True})
