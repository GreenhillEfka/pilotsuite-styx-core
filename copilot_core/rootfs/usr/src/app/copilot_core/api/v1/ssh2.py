from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ssh2_bp = Blueprint("ssh2", __name__, url_prefix="/api/v1/ssh2")
@ssh2_bp.route("", methods=["GET"])
@require_token
def ssh2(): return jsonify({"ok": True})
