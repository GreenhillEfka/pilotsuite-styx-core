from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
wec_bp = Blueprint("wec", __name__, url_prefix="/api/v1/wec")
@wec_bp.route("", methods=["GET"])
@require_token
def wec(): return jsonify({"ok": True})
