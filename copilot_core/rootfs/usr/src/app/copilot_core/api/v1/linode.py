from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
linode_bp = Blueprint("linode", __name__, url_prefix="/api/v1/linode")
@linode_bp.route("", methods=["GET"])
@require_token
def linode(): return jsonify({"ok": True})
