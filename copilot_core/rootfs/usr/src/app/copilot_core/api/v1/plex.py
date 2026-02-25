from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
plex_bp = Blueprint("plex", __name__, url_prefix="/api/v1/plex")
@plex_bp.route("", methods=["GET"])
@require_token
def plex(): return jsonify({"ok": True})
