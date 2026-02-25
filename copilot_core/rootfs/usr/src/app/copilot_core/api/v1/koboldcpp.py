from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
koboldcpp_bp = Blueprint("koboldcpp", __name__, url_prefix="/api/v1/koboldcpp")
@koboldcpp_bp.route("", methods=["GET"])
@require_token
def koboldcpp(): return jsonify({"ok": True})
