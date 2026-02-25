from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
jaeger_bp = Blueprint("jaeger", __name__, url_prefix="/api/v1/jaeger")
@jaeger_bp.route("", methods=["GET"])
@require_token
def jaeger(): return jsonify({"ok": True})
