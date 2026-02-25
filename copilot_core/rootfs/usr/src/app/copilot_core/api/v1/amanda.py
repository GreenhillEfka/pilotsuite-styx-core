from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
amanda_bp = Blueprint("amanda", __name__, url_prefix="/api/v1/amanda")
@amanda_bp.route("", methods=["GET"])
@require_token
def amanda(): return jsonify({"ok": True})
