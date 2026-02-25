from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
alertmanager_bp = Blueprint("alertmanager", __name__, url_prefix="/api/v1/alertmanager")
@alertmanager_bp.route("", methods=["GET"])
@require_token
def alertmanager(): return jsonify({"ok": True})
