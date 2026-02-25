from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
zk_bp = Blueprint("zk", __name__, url_prefix="/api/v1/zk")
@zk_bp.route("", methods=["GET"])
@require_token
def zk(): return jsonify({"ok": True})
