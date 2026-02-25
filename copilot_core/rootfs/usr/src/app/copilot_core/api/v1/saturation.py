from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
saturation_bp = Blueprint("saturation", __name__, url_prefix="/api/v1/saturation")
@saturation_bp.route("", methods=["GET"])
@require_token
def saturation(): return jsonify({"ok": True})
