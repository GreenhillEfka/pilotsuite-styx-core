from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
hue_bp = Blueprint("hue", __name__, url_prefix="/api/v1/hue")
@hue_bp.route("", methods=["GET"])
@require_token
def hue(): return jsonify({"ok": True})
