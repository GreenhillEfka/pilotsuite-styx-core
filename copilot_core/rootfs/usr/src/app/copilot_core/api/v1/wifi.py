from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
wifi_bp = Blueprint("wifi", __name__, url_prefix="/api/v1/wifi")
@wifi_bp.route("", methods=["GET"])
@require_token
def wifi(): return jsonify({"ok": True})
