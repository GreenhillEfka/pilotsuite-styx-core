from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
rocm_bp = Blueprint("rocm", __name__, url_prefix="/api/v1/rocm")
@rocm_bp.route("", methods=["GET"])
@require_token
def rocm(): return jsonify({"ok": True})
