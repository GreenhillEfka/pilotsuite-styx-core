from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
tty_bp = Blueprint("tty", __name__, url_prefix="/api/v1/tty")
@tty_bp.route("", methods=["GET"])
@require_token
def tty(): return jsonify({"ok": True})
