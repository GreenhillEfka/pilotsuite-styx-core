from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
nginx_ing_bp = Blueprint("nginx_ing", __name__, url_prefix="/api/v1/nginx_ing")
@nginx_ing_bp.route("", methods=["GET"])
@require_token
def nginx_ing(): return jsonify({"ok": True})
