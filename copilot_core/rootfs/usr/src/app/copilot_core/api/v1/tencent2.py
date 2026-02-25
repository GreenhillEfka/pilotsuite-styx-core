from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
tencent_bp = Blueprint("tencent2", __name__, url_prefix="/api/v1/tencent2")
@tencent_bp.route("", methods=["GET"])
@require_token
def tencent2(): return jsonify({"ok": True})
