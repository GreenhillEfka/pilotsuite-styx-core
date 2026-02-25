from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
kasten_bp = Blueprint("kasten", __name__, url_prefix="/api/v1/kasten")
@kasten_bp.route("", methods=["GET"])
@require_token
def kasten(): return jsonify({"ok": True})
