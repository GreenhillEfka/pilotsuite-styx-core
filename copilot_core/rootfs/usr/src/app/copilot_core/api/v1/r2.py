from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
r2_bp = Blueprint("r2", __name__, url_prefix="/api/v1/r2")
@r2_bp.route("", methods=["GET"])
@require_token
def r2(): return jsonify({"ok": True})
