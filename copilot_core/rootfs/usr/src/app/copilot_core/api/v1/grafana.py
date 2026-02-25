from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
grafana_bp = Blueprint("grafana", __name__, url_prefix="/api/v1/grafana")
@grafana_bp.route("", methods=["GET"])
@require_token
def grafana(): return jsonify({"ok": True})
