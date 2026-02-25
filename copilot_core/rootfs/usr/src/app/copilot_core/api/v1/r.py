from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
r_bp = Blueprint("r", __name__, url_prefix="/api/v1/r")
@r_bp.route("", methods=["GET"])
@require_token
def r(): return jsonify({"ok": True})
