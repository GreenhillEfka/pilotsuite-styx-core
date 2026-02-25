from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
matomo_bp = Blueprint("matomo", __name__, url_prefix="/api/v1/matomo")
@matomo_bp.route("", methods=["GET"])
@require_token
def matomo(): return jsonify({"ok": True})
