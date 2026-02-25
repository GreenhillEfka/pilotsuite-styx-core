from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
newrelic_bp = Blueprint("newrelic", __name__, url_prefix="/api/v1/newrelic")
@newrelic_bp.route("", methods=["GET"])
@require_token
def newrelic(): return jsonify({"ok": True})
