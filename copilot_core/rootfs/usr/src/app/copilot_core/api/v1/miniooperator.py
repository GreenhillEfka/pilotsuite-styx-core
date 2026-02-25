from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
miniooperator_bp = Blueprint("miniooperator", __name__, url_prefix="/api/v1/miniooperator")
@miniooperator_bp.route("", methods=["GET"])
@require_token
def miniooperator(): return jsonify({"ok": True})
