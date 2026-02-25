from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
triton_bp = Blueprint("triton", __name__, url_prefix="/api/v1/triton")
@triton_bp.route("", methods=["GET"])
@require_token
def triton(): return jsonify({"ok": True})
