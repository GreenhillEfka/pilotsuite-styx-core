from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
render_bp = Blueprint("render", __name__, url_prefix="/api/v1/render")
@render_bp.route("", methods=["GET"])
@require_token
def render(): return jsonify({"ok": True})
