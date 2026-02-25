from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
memory_bp = Blueprint("memory", __name__, url_prefix="/api/v1/memory")
@memory_bp.route("", methods=["GET"])
@require_token
def memory(): return jsonify({"ok": True})
