from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
brightness_bp = Blueprint("brightness", __name__, url_prefix="/api/v1/brightness")
@brightness_bp.route("", methods=["GET"])
@require_token
def brightness(): return jsonify({"ok": True})
