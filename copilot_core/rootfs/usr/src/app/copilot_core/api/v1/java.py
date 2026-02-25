from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
java_bp = Blueprint("java", __name__, url_prefix="/api/v1/java")
@java_bp.route("", methods=["GET"])
@require_token
def java(): return jsonify({"ok": True})
