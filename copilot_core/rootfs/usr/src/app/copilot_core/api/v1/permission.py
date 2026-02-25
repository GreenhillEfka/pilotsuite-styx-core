from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
permission_bp = Blueprint("permission", __name__, url_prefix="/api/v1/permission")
@permission_bp.route("", methods=["GET"])
@require_token
def permission(): return jsonify({"ok": True})
