from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
k0s_bp = Blueprint("k0s", __name__, url_prefix="/api/v1/k0s")
@k0s_bp.route("", methods=["GET"])
@require_token
def k0s(): return jsonify({"ok": True})
