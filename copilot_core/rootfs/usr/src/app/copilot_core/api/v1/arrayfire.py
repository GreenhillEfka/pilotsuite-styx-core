from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
arrayfire_bp = Blueprint("arrayfire", __name__, url_prefix="/api/v1/arrayfire")
@arrayfire_bp.route("", methods=["GET"])
@require_token
def arrayfire(): return jsonify({"ok": True})
