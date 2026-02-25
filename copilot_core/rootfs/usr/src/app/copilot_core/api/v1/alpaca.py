from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
alpaca_bp = Blueprint("alpaca", __name__, url_prefix="/api/v1/alpaca")
@alpaca_bp.route("", methods=["GET"])
@require_token
def alpaca(): return jsonify({"ok": True})
