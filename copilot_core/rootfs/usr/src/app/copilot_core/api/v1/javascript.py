from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
javascript_bp = Blueprint("javascript", __name__, url_prefix="/api/v1/javascript")
@javascript_bp.route("", methods=["GET"])
@require_token
def javascript(): return jsonify({"ok": True})
