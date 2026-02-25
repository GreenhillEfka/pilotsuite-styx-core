from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
d1_bp = Blueprint("d1", __name__, url_prefix="/api/v1/d1")
@d1_bp.route("", methods=["GET"])
@require_token
def d1(): return jsonify({"ok": True})
