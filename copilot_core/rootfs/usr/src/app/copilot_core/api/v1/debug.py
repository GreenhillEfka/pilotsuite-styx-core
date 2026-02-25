from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
debug_bp = Blueprint("debug", __name__, url_prefix="/api/v1/debug")
@debug_bp.route("", methods=["GET"])
@require_token
def debug(): return jsonify({"ok": True})
