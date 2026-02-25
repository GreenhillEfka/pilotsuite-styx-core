from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
postman_bp = Blueprint("postman", __name__, url_prefix="/api/v1/postman")
@postman_bp.route("", methods=["GET"])
@require_token
def postman(): return jsonify({"ok": True})
