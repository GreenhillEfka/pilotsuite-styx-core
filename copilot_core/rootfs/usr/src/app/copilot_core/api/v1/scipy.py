from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
scipy_bp = Blueprint("scipy", __name__, url_prefix="/api/v1/scipy")
@scipy_bp.route("", methods=["GET"])
@require_token
def scipy(): return jsonify({"ok": True})
