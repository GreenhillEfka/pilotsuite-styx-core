from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
baikal_bp = Blueprint("baikal", __name__, url_prefix="/api/v1/baikal")
@baikal_bp.route("", methods=["GET"])
@require_token
def baikal(): return jsonify({"ok": True})
