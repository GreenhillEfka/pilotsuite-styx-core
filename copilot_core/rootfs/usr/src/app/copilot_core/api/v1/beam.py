from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
beam_bp = Blueprint("beam", __name__, url_prefix="/api/v1/beam")
@beam_bp.route("", methods=["GET"])
@require_token
def beam(): return jsonify({"ok": True})
