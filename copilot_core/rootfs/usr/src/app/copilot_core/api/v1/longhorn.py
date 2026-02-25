from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
longhorn_bp = Blueprint("longhorn", __name__, url_prefix="/api/v1/longhorn")
@longhorn_bp.route("", methods=["GET"])
@require_token
def longhorn(): return jsonify({"ok": True})
