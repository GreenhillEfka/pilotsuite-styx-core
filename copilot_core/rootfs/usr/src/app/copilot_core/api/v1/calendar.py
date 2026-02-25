from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
calendar_bp = Blueprint("calendar", __name__, url_prefix="/api/v1/calendar")
@calendar_bp.route("", methods=["GET"])
@require_token
def calendar(): return jsonify({"ok": True})
