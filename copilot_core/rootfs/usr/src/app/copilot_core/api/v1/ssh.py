from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ssh_bp = Blueprint("ssh", __name__, url_prefix="/api/v1/ssh")
@ssh_bp.route("", methods=["GET"])
@require_token
def ssh(): return jsonify({"ok": True})
