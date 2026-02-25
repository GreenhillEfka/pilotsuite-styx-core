from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
stoplight_bp = Blueprint("stoplight", __name__, url_prefix="/api/v1/stoplight")
@stoplight_bp.route("", methods=["GET"])
@require_token
def stoplight(): return jsonify({"ok": True})
