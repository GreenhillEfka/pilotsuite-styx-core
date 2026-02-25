from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
telnet2_bp = Blueprint("telnet2", __name__, url_prefix="/api/v1/telnet2")
@telnet2_bp.route("", methods=["GET"])
@require_token
def telnet2(): return jsonify({"ok": True})
