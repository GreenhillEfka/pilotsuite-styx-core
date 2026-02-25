from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
raid_bp = Blueprint("raid", __name__, url_prefix="/api/v1/raid")
@raid_bp.route("", methods=["GET"])
@require_token
def raid(): return jsonify({"ok": True})
