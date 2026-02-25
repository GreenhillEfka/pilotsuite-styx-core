from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
lens_bp = Blueprint("lens", __name__, url_prefix="/api/v1/lens")
@lens_bp.route("", methods=["GET"])
@require_token
def lens(): return jsonify({"ok": True})
