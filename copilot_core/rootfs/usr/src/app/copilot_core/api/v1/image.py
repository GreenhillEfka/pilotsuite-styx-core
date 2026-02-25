from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
image_bp = Blueprint("image", __name__, url_prefix="/api/v1/image")
@image_bp.route("", methods=["GET"])
@require_token
def image(): return jsonify({"ok": True})
