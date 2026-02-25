from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
humidifier_bp = Blueprint("humidifier", __name__, url_prefix="/api/v1/humidifier")
@humidifier_bp.route("", methods=["GET"])
@require_token
def humidifier(): return jsonify({"ok": True})
