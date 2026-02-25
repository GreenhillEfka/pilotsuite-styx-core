from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
eigen_bp = Blueprint("eigen", __name__, url_prefix="/api/v1/eigen")
@eigen_bp.route("", methods=["GET"])
@require_token
def eigen(): return jsonify({"ok": True})
