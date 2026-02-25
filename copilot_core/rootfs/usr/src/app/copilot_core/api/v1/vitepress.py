from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
vitepress_bp = Blueprint("vitepress", __name__, url_prefix="/api/v1/vitepress")
@vitepress_bp.route("", methods=["GET"])
@require_token
def vitepress(): return jsonify({"ok": True})
