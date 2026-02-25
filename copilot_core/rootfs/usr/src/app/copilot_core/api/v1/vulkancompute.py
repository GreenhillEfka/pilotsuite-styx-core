from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
vulkancompute_bp = Blueprint("vulkancompute", __name__, url_prefix="/api/v1/vulkancompute")
@vulkancompute_bp.route("", methods=["GET"])
@require_token
def vulkancompute(): return jsonify({"ok": True})
