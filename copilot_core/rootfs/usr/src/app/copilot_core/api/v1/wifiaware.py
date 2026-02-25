from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
wifiaware_bp = Blueprint("wifiaware", __name__, url_prefix="/api/v1/wifiaware")
@wifiaware_bp.route("", methods=["GET"])
@require_token
def wifiaware(): return jsonify({"ok": True})
