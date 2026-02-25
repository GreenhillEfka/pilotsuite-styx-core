from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
aspect_bp = Blueprint("aspect", __name__, url_prefix="/api/v1/aspect")
@aspect_bp.route("", methods=["GET"])
@require_token
def aspect(): return jsonify({"ok": True})
