from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
k3s_bp = Blueprint("k3s", __name__, url_prefix="/api/v1/k3s")
@k3s_bp.route("", methods=["GET"])
@require_token
def k3s(): return jsonify({"ok": True})
