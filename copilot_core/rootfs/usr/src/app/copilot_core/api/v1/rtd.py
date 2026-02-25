from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
rtd_bp = Blueprint("rtd", __name__, url_prefix="/api/v1/rtd")
@rtd_bp.route("", methods=["GET"])
@require_token
def rtd(): return jsonify({"ok": True})
