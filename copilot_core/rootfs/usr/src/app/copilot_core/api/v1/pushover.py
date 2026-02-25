from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pushover_bp = Blueprint("pushover", __name__, url_prefix="/api/v1/pushover")
@pushover_bp.route("", methods=["GET"])
@require_token
def pushover(): return jsonify({"ok": True})
