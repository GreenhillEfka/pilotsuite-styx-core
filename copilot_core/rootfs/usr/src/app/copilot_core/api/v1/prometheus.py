from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
prometheus_bp = Blueprint("prometheus", __name__, url_prefix="/api/v1/prometheus")
@prometheus_bp.route("", methods=["GET"])
@require_token
def prometheus(): return jsonify({"ok": True})
