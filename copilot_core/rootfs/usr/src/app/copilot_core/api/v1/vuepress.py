from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
vuepress_bp = Blueprint("vuepress", __name__, url_prefix="/api/v1/vuepress")
@vuepress_bp.route("", methods=["GET"])
@require_token
def vuepress(): return jsonify({"ok": True})
