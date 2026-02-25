from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
swagger_bp = Blueprint("swagger", __name__, url_prefix="/api/v1/swagger")
@swagger_bp.route("", methods=["GET"])
@require_token
def swagger(): return jsonify({"ok": True})
