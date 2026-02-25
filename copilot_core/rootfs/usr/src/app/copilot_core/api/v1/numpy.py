from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
numpy_bp = Blueprint("numpy", __name__, url_prefix="/api/v1/numpy")
@numpy_bp.route("", methods=["GET"])
@require_token
def numpy(): return jsonify({"ok": True})
