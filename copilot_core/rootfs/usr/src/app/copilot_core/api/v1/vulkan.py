from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
vulkan_bp = Blueprint("vulkan", __name__, url_prefix="/api/v1/vulkan")
@vulkan_bp.route("", methods=["GET"])
@require_token
def vulkan(): return jsonify({"ok": True})
