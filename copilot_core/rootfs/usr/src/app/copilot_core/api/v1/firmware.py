from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
firmware_bp = Blueprint("firmware", __name__, url_prefix="/api/v1/firmware")
@firmware_bp.route("", methods=["GET"])
@require_token
def firmware(): return jsonify({"ok": True})
