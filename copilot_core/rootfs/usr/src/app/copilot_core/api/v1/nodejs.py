from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
nodejs_bp = Blueprint("nodejs", __name__, url_prefix="/api/v1/nodejs")
@nodejs_bp.route("", methods=["GET"])
@require_token
def nodejs(): return jsonify({"ok": True})
