from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
bugsnag_bp = Blueprint("bugsnag", __name__, url_prefix="/api/v1/bugsnag")
@bugsnag_bp.route("", methods=["GET"])
@require_token
def bugsnag(): return jsonify({"ok": True})
