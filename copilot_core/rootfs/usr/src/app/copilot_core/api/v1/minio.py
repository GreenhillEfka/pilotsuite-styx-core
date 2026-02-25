from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
minio_bp = Blueprint("minio", __name__, url_prefix="/api/v1/minio")
@minio_bp.route("", methods=["GET"])
@require_token
def minio(): return jsonify({"ok": True})
