from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ghost_bp = Blueprint("ghost", __name__, url_prefix="/api/v1/ghost")
@ghost_bp.route("", methods=["GET"])
@require_token
def ghost(): return jsonify({"ok": True})
