from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
status_bp = Blueprint("status2", __name__, url_prefix="/api/v1/status2")
@status_bp.route("", methods=["GET"])
@require_token
def status(): return jsonify({"ok": True})
