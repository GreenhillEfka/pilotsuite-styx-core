from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
linode2_bp = Blueprint("linode2", __name__, url_prefix="/api/v1/linode2")
@linode2_bp.route("", methods=["GET"])
@require_token
def linode2(): return jsonify({"ok": True})
