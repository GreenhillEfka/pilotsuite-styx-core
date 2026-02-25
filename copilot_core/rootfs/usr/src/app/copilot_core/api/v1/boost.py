from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
boost_bp = Blueprint("boost", __name__, url_prefix="/api/v1/boost")
@boost_bp.route("", methods=["GET"])
@require_token
def boost(): return jsonify({"ok": True})
