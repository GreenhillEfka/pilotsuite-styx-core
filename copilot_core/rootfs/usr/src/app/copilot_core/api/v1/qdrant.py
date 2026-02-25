from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
qdrant_bp = Blueprint("qdrant", __name__, url_prefix="/api/v1/qdrant")
@qdrant_bp.route("", methods=["GET"])
@require_token
def qdrant(): return jsonify({"ok": True})
