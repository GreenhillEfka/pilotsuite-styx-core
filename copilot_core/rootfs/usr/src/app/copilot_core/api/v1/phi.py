from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
phi_bp = Blueprint("phi", __name__, url_prefix="/api/v1/phi")
@phi_bp.route("", methods=["GET"])
@require_token
def phi(): return jsonify({"ok": True})
