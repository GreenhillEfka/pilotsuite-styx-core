from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
lemmy_bp = Blueprint("lemmy", __name__, url_prefix="/api/v1/lemmy")
@lemmy_bp.route("", methods=["GET"])
@require_token
def lemmy(): return jsonify({"ok": True})
