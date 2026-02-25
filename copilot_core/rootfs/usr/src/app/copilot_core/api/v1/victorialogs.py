from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
victorialogs_bp = Blueprint("victorialogs", __name__, url_prefix="/api/v1/victorialogs")
@victorialogs_bp.route("", methods=["GET"])
@require_token
def victorialogs(): return jsonify({"ok": True})
