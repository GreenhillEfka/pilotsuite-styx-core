from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
kotlin_bp = Blueprint("kotlin", __name__, url_prefix="/api/v1/kotlin")
@kotlin_bp.route("", methods=["GET"])
@require_token
def kotlin(): return jsonify({"ok": True})
