from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
radicale_bp = Blueprint("radicale", __name__, url_prefix="/api/v1/radicale")
@radicale_bp.route("", methods=["GET"])
@require_token
def radicale(): return jsonify({"ok": True})
