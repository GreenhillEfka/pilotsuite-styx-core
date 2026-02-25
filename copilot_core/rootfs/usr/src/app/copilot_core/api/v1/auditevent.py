from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
auditevent_bp = Blueprint("auditevent", __name__, url_prefix="/api/v1/auditevent")
@auditevent_bp.route("", methods=["GET"])
@require_token
def auditevent(): return jsonify({"ok": True})
