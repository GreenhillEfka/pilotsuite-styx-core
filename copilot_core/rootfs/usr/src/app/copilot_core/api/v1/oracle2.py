from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
oracle2_bp = Blueprint("oracle2", __name__, url_prefix="/api/v1/oracle2")
@oracle2_bp.route("", methods=["GET"])
@require_token
def oracle2(): return jsonify({"ok": True})
