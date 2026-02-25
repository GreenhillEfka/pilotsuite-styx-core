from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
version2_bp = Blueprint("version2", __name__, url_prefix="/api/v1/version2")
@version2_bp.route("", methods=["GET"])
@require_token
def version2(): return jsonify({"ok": True})
