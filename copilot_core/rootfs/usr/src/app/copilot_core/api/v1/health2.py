from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
health_bp = Blueprint("health2", __name__, url_prefix="/api/v1/health2")
@health_bp.route("", methods=["GET"])
@require_token
def health(): return jsonify({"ok": True})
