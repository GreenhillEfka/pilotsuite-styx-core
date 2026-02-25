from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
rclone_bp = Blueprint("rclone", __name__, url_prefix="/api/v1/rclone")
@rclone_bp.route("", methods=["GET"])
@require_token
def rclone(): return jsonify({"ok": True})
