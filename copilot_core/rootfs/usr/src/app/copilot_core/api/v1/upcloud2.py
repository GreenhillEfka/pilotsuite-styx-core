from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
upcloud_bp = Blueprint("upcloud2", __name__, url_prefix="/api/v1/upcloud2")
@upcloud_bp.route("", methods=["GET"])
@require_token
def upcloud2(): return jsonify({"ok": True})
