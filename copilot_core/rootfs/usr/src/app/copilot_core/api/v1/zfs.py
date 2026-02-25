from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
zfs_bp = Blueprint("zfs", __name__, url_prefix="/api/v1/zfs")
@zfs_bp.route("", methods=["GET"])
@require_token
def zfs(): return jsonify({"ok": True})
