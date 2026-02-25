from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
otc_bp = Blueprint("otc", __name__, url_prefix="/api/v1/otc")
@otc_bp.route("", methods=["GET"])
@require_token
def otc(): return jsonify({"ok": True})
