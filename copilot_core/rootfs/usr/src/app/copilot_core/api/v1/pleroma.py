from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pleroma_bp = Blueprint("pleroma", __name__, url_prefix="/api/v1/pleroma")
@pleroma_bp.route("", methods=["GET"])
@require_token
def pleroma(): return jsonify({"ok": True})
