from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
light_bp = Blueprint("light", __name__, url_prefix="/api/v1/light")
@light_bp.route("", methods=["GET"])
@require_token
def light(): return jsonify({"ok": True})
