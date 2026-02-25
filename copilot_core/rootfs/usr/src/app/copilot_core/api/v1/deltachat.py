from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
deltachat_bp = Blueprint("deltachat", __name__, url_prefix="/api/v1/deltachat")
@deltachat_bp.route("", methods=["GET"])
@require_token
def deltachat(): return jsonify({"ok": True})
