from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
btrfs_bp = Blueprint("btrfs", __name__, url_prefix="/api/v1/btrfs")
@btrfs_bp.route("", methods=["GET"])
@require_token
def btrfs(): return jsonify({"ok": True})
