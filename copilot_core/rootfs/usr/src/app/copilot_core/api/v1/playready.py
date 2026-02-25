from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
playready_bp = Blueprint("playready", __name__, url_prefix="/api/v1/playready")
@playready_bp.route("", methods=["GET"])
@require_token
def playready(): return jsonify({"ok": True})
