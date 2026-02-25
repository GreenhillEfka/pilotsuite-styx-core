from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ray_bp = Blueprint("ray", __name__, url_prefix="/api/v1/ray")
@ray_bp.route("", methods=["GET"])
@require_token
def ray(): return jsonify({"ok": True})
