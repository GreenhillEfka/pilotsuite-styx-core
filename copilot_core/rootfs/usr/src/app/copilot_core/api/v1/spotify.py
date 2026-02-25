from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
spotify_bp = Blueprint("spotify", __name__, url_prefix="/api/v1/spotify")
@spotify_bp.route("", methods=["GET"])
@require_token
def spotify(): return jsonify({"ok": True})
