from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
camera_bp = Blueprint("camera", __name__, url_prefix="/api/v1/camera")
@camera_bp.route("", methods=["GET"])
@require_token
def camera(): return jsonify({"ok": True})
