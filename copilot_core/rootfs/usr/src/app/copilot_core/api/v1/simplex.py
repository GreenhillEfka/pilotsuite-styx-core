from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
simplex_bp = Blueprint("simplex", __name__, url_prefix="/api/v1/simplex")
@simplex_bp.route("", methods=["GET"])
@require_token
def simplex(): return jsonify({"ok": True})
