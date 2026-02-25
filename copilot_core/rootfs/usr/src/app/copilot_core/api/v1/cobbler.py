from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
cobbler_bp = Blueprint("cobbler", __name__, url_prefix="/api/v1/cobbler")
@cobbler_bp.route("", methods=["GET"])
@require_token
def cobbler(): return jsonify({"ok": True})
