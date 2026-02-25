from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
lambdalabs_bp = Blueprint("lambdalabs", __name__, url_prefix="/api/v1/lambdalabs")
@lambdalabs_bp.route("", methods=["GET"])
@require_token
def lambdalabs(): return jsonify({"ok": True})
