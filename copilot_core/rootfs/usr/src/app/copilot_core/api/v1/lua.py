from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
lua_bp = Blueprint("lua", __name__, url_prefix="/api/v1/lua")
@lua_bp.route("", methods=["GET"])
@require_token
def lua(): return jsonify({"ok": True})
