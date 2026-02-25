from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
cellular_bp = Blueprint("cellular", __name__, url_prefix="/api/v1/cellular")
@cellular_bp.route("", methods=["GET"])
@require_token
def cellular(): return jsonify({"ok": True})
