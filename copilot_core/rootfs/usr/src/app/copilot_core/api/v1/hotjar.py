from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
hotjar_bp = Blueprint("hotjar", __name__, url_prefix="/api/v1/hotjar")
@hotjar_bp.route("", methods=["GET"])
@require_token
def hotjar(): return jsonify({"ok": True})
