from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
torchserve_bp = Blueprint("torchserve", __name__, url_prefix="/api/v1/torchserve")
@torchserve_bp.route("", methods=["GET"])
@require_token
def torchserve(): return jsonify({"ok": True})
