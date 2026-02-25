from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
ufs_bp = Blueprint("ufs", __name__, url_prefix="/api/v1/ufs")
@ufs_bp.route("", methods=["GET"])
@require_token
def ufs(): return jsonify({"ok": True})
