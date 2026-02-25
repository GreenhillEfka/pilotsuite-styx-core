from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
amavis_bp = Blueprint("amavis", __name__, url_prefix="/api/v1/amavis")
@amavis_bp.route("", methods=["GET"])
@require_token
def amavis(): return jsonify({"ok": True})
