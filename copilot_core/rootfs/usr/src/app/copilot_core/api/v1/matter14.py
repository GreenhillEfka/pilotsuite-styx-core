from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
matter14_bp = Blueprint("matter14", __name__, url_prefix="/api/v1/matter14")
@matter14_bp.route("", methods=["GET"])
@require_token
def matter14(): return jsonify({"ok": True})
