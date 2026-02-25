from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
tencent_bp = Blueprint("tencent", __name__, url_prefix="/api/v1/tencent")
@tencent_bp.route("", methods=["GET"])
@require_token
def tencent(): return jsonify({"ok": True})
