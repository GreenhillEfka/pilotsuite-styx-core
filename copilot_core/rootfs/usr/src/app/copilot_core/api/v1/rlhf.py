from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
rlhf_bp = Blueprint("rlhf", __name__, url_prefix="/api/v1/rlhf")
@rlhf_bp.route("", methods=["GET"])
@require_token
def rlhf(): return jsonify({"ok": True})
