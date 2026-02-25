from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
telnet_bp = Blueprint("telnet", __name__, url_prefix="/api/v1/telnet")
@telnet_bp.route("", methods=["GET"])
@require_token
def telnet(): return jsonify({"ok": True})
