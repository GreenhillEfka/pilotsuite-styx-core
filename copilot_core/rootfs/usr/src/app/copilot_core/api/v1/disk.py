from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
disk_bp = Blueprint("disk", __name__, url_prefix="/api/v1/disk")
@disk_bp.route("", methods=["GET"])
@require_token
def disk(): return jsonify({"ok": True})
