from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
bruno_bp = Blueprint("bruno", __name__, url_prefix="/api/v1/bruno")
@bruno_bp.route("", methods=["GET"])
@require_token
def bruno(): return jsonify({"ok": True})
