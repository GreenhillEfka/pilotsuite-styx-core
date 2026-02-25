from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
b2_bp = Blueprint("b2", __name__, url_prefix="/api/v1/b2")
@b2_bp.route("", methods=["GET"])
@require_token
def b2(): return jsonify({"ok": True})
