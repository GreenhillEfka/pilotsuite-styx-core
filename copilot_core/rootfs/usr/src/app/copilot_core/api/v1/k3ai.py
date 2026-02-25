from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
k3ai_bp = Blueprint("k3ai", __name__, url_prefix="/api/v1/k3ai")
@k3ai_bp.route("", methods=["GET"])
@require_token
def k3ai(): return jsonify({"ok": True})
