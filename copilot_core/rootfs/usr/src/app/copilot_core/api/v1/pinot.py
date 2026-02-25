from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pinot_bp = Blueprint("pinot", __name__, url_prefix="/api/v1/pinot")
@pinot_bp.route("", methods=["GET"])
@require_token
def pinot(): return jsonify({"ok": True})
