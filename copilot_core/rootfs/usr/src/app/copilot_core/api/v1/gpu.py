from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
gpu_bp = Blueprint("gpu", __name__, url_prefix="/api/v1/gpu")
@gpu_bp.route("", methods=["GET"])
@require_token
def gpu(): return jsonify({"ok": True})
