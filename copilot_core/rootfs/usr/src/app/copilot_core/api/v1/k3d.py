from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
k3d_bp = Blueprint("k3d", __name__, url_prefix="/api/v1/k3d")
@k3d_bp.route("", methods=["GET"])
@require_token
def k3d(): return jsonify({"ok": True})
