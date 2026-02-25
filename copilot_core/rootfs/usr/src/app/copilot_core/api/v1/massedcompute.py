from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
massedcompute_bp = Blueprint("massedcompute", __name__, url_prefix="/api/v1/massedcompute")
@massedcompute_bp.route("", methods=["GET"])
@require_token
def massedcompute(): return jsonify({"ok": True})
