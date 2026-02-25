from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
zig_bp = Blueprint("zig", __name__, url_prefix="/api/v1/zig")
@zig_bp.route("", methods=["GET"])
@require_token
def zig(): return jsonify({"ok": True})
