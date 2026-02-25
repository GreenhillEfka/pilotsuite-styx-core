from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
xfs_bp = Blueprint("xfs", __name__, url_prefix="/api/v1/xfs")
@xfs_bp.route("", methods=["GET"])
@require_token
def xfs(): return jsonify({"ok": True})
