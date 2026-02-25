from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
planetscale_bp = Blueprint("planetscale", __name__, url_prefix="/api/v1/planetscale")
@planetscale_bp.route("", methods=["GET"])
@require_token
def planetscale(): return jsonify({"ok": True})
