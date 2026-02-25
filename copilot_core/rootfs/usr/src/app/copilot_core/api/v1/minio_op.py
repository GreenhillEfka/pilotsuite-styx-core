from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
minio_op_bp = Blueprint("minio_op", __name__, url_prefix="/api/v1/minio_op")
@minio_op_bp.route("", methods=["GET"])
@require_token
def minio_op(): return jsonify({"ok": True})
