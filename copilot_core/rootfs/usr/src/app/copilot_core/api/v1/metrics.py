from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
metrics_bp = Blueprint("metrics", __name__, url_prefix="/api/v1/metrics")
@metrics_bp.route("", methods=["GET"])
@require_token
def metrics(): return jsonify({"ok": True})
