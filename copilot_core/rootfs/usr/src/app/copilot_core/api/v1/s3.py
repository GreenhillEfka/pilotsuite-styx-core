from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
s3_bp = Blueprint("s3", __name__, url_prefix="/api/v1/s3")
@s3_bp.route("", methods=["GET"])
@require_token
def s3(): return jsonify({"ok": True})
