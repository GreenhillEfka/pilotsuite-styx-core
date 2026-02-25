from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
thunderbolt_bp = Blueprint("thunderbolt", __name__, url_prefix="/api/v1/thunderbolt")
@thunderbolt_bp.route("", methods=["GET"])
@require_token
def thunderbolt(): return jsonify({"ok": True})
