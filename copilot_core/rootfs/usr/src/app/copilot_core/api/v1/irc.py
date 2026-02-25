from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
irc_bp = Blueprint("irc", __name__, url_prefix="/api/v1/irc")
@irc_bp.route("", methods=["GET"])
@require_token
def irc(): return jsonify({"ok": True})
