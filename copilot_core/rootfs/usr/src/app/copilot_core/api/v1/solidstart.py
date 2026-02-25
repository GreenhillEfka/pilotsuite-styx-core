from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
solidstart_bp = Blueprint("solidstart", __name__, url_prefix="/api/v1/solidstart")
@solidstart_bp.route("", methods=["GET"])
@require_token
def solidstart(): return jsonify({"ok": True})
