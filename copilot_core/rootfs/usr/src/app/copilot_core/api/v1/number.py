from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
number_bp = Blueprint("number", __name__, url_prefix="/api/v1/number")
@number_bp.route("", methods=["GET"])
@require_token
def number(): return jsonify({"ok": True})
