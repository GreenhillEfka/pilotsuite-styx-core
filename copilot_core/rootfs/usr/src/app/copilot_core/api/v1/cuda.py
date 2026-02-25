from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
cuda_bp = Blueprint("cuda", __name__, url_prefix="/api/v1/cuda")
@cuda_bp.route("", methods=["GET"])
@require_token
def cuda(): return jsonify({"ok": True})
