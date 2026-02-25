from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
contour_bp = Blueprint("contour", __name__, url_prefix="/api/v1/contour")
@contour_bp.route("", methods=["GET"])
@require_token
def contour(): return jsonify({"ok": True})
