from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
flink_bp = Blueprint("flink", __name__, url_prefix="/api/v1/flink")
@flink_bp.route("", methods=["GET"])
@require_token
def flink(): return jsonify({"ok": True})
