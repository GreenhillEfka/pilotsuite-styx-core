from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
c_bp = Blueprint("c", __name__, url_prefix="/api/v1/c")
@c_bp.route("", methods=["GET"])
@require_token
def c(): return jsonify({"ok": True})
