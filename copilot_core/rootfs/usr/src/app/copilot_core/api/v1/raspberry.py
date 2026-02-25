from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
raspberry_bp = Blueprint("raspberry", __name__, url_prefix="/api/v1/raspberry")
@raspberry_bp.route("", methods=["GET"])
@require_token
def raspberry(): return jsonify({"ok": True})
