from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
pop3_bp = Blueprint("pop3", __name__, url_prefix="/api/v1/pop3")
@pop3_bp.route("", methods=["GET"])
@require_token
def pop3(): return jsonify({"ok": True})
