from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
nscd_bp = Blueprint("nscd", __name__, url_prefix="/api/v1/nscd")
@nscd_bp.route("", methods=["GET"])
@require_token
def nscd(): return jsonify({"ok": True})
