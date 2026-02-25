from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
switch_bp = Blueprint("switch_v2", __name__, url_prefix="/api/v1/switch_v2")
@switch_bp.route("", methods=["GET"])
@require_token
def switch_v2(): return jsonify({"ok": True})
