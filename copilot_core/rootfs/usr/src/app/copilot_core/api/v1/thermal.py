from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
thermal_bp = Blueprint("thermal", __name__, url_prefix="/api/v1/thermal")
@thermal_bp.route("", methods=["GET"])
@require_token
def thermal(): return jsonify({"ok": True})
