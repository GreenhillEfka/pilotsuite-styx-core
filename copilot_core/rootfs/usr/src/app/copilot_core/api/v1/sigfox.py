from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
sigfox_bp = Blueprint("sigfox", __name__, url_prefix="/api/v1/sigfox")
@sigfox_bp.route("", methods=["GET"])
@require_token
def sigfox(): return jsonify({"ok": True})
