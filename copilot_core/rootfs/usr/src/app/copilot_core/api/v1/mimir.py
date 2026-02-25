from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
mimir_bp = Blueprint("mimir", __name__, url_prefix="/api/v1/mimir")
@mimir_bp.route("", methods=["GET"])
@require_token
def mimir(): return jsonify({"ok": True})
