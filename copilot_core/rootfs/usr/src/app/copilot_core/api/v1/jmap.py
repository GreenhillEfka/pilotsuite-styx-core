from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
jmap_bp = Blueprint("jmap", __name__, url_prefix="/api/v1/jmap")
@jmap_bp.route("", methods=["GET"])
@require_token
def jmap(): return jsonify({"ok": True})
