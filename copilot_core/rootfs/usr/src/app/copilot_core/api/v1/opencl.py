from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
opencl_bp = Blueprint("opencl", __name__, url_prefix="/api/v1/opencl")
@opencl_bp.route("", methods=["GET"])
@require_token
def opencl(): return jsonify({"ok": True})
