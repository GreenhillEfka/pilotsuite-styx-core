from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
minio2_bp = Blueprint("minio2", __name__, url_prefix="/api/v1/minio2")
@minio2_bp.route("", methods=["GET"])
@require_token
def minio2(): return jsonify({"ok": True})
