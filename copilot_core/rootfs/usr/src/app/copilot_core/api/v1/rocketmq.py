from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
rocketmq_bp = Blueprint("rocketmq", __name__, url_prefix="/api/v1/rocketmq")
@rocketmq_bp.route("", methods=["GET"])
@require_token
def rocketmq(): return jsonify({"ok": True})
