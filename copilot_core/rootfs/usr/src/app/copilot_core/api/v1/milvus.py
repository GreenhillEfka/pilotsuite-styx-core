from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
milvus_bp = Blueprint("milvus", __name__, url_prefix="/api/v1/milvus")
@milvus_bp.route("", methods=["GET"])
@require_token
def milvus(): return jsonify({"ok": True})
