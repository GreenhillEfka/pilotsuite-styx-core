from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
sycl_bp = Blueprint("sycl", __name__, url_prefix="/api/v1/sycl")
@sycl_bp.route("", methods=["GET"])
@require_token
def sycl(): return jsonify({"ok": True})
