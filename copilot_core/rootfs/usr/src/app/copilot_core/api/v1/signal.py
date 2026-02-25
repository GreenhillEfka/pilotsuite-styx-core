from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
signal_bp = Blueprint("signal", __name__, url_prefix="/api/v1/signal")
@signal_bp.route("", methods=["GET"])
@require_token
def signal(): return jsonify({"ok": True})
