from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
promop_bp = Blueprint("promop", __name__, url_prefix="/api/v1/promop")
@promop_bp.route("", methods=["GET"])
@require_token
def promop(): return jsonify({"ok": True})
