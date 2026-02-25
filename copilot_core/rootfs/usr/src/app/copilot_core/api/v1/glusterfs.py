from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
glusterfs_bp = Blueprint("glusterfs", __name__, url_prefix="/api/v1/glusterfs")
@glusterfs_bp.route("", methods=["GET"])
@require_token
def glusterfs(): return jsonify({"ok": True})
