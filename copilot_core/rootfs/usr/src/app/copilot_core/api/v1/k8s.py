from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
k8s_bp = Blueprint("k8s", __name__, url_prefix="/api/v1/k8s")
@k8s_bp.route("", methods=["GET"])
@require_token
def k8s(): return jsonify({"ok": True})
