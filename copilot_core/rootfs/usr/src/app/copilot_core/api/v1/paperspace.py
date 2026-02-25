from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
paperspace_bp = Blueprint("paperspace", __name__, url_prefix="/api/v1/paperspace")
@paperspace_bp.route("", methods=["GET"])
@require_token
def paperspace(): return jsonify({"ok": True})
