from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
swaggerui_bp = Blueprint("swaggerui", __name__, url_prefix="/api/v1/swaggerui")
@swaggerui_bp.route("", methods=["GET"])
@require_token
def swaggerui(): return jsonify({"ok": True})
