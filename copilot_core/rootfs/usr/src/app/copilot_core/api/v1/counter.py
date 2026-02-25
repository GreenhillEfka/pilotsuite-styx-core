from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
counter_bp = Blueprint("counter", __name__, url_prefix="/api/v1/counter")
@counter_bp.route("", methods=["GET"])
@require_token
def counter(): return jsonify({"ok": True})
