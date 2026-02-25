from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
reasonml_bp = Blueprint("reasonml", __name__, url_prefix="/api/v1/reasonml")
@reasonml_bp.route("", methods=["GET"])
@require_token
def reasonml(): return jsonify({"ok": True})
