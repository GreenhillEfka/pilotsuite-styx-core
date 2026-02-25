from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
eks_bp = Blueprint("eks", __name__, url_prefix="/api/v1/eks")
@eks_bp.route("", methods=["GET"])
@require_token
def eks(): return jsonify({"ok": True})
