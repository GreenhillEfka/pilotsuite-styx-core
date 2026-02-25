from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
hexo_bp = Blueprint("hexo", __name__, url_prefix="/api/v1/hexo")
@hexo_bp.route("", methods=["GET"])
@require_token
def hexo(): return jsonify({"ok": True})
