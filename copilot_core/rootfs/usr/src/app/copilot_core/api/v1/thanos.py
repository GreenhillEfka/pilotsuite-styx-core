from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
thanos_bp = Blueprint("thanos", __name__, url_prefix="/api/v1/thanos")
@thanos_bp.route("", methods=["GET"])
@require_token
def thanos(): return jsonify({"ok": True})
