from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
media2_bp = Blueprint("media2", __name__, url_prefix="/api/v1/media2")
@media2_bp.route("", methods=["GET"])
@require_token
def media2(): return jsonify({"ok": True})
