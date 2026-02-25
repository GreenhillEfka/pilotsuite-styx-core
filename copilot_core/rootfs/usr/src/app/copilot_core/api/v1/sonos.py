from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
sonos_bp = Blueprint("sonos", __name__, url_prefix="/api/v1/sonos")
@sonos_bp.route("", methods=["GET"])
@require_token
def sonos(): return jsonify({"ok": True})
