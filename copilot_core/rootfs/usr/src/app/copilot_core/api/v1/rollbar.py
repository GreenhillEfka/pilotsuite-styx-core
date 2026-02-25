from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
rollbar_bp = Blueprint("rollbar", __name__, url_prefix="/api/v1/rollbar")
@rollbar_bp.route("", methods=["GET"])
@require_token
def rollbar(): return jsonify({"ok": True})
