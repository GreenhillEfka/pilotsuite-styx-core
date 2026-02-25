from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
k9s_bp = Blueprint("k9s", __name__, url_prefix="/api/v1/k9s")
@k9s_bp.route("", methods=["GET"])
@require_token
def k9s(): return jsonify({"ok": True})
