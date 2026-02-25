from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
throttle_bp = Blueprint("throttle", __name__, url_prefix="/api/v1/throttle")
@throttle_bp.route("", methods=["GET"])
@require_token
def throttle(): return jsonify({"ok": True})
