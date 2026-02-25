from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
dash_bp = Blueprint("dash", __name__, url_prefix="/api/v1/dash")
@dash_bp.route("", methods=["GET"])
@require_token
def dash(): return jsonify({"ok": True})
