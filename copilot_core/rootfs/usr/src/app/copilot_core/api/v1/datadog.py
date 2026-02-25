from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
datadog_bp = Blueprint("datadog", __name__, url_prefix="/api/v1/datadog")
@datadog_bp.route("", methods=["GET"])
@require_token
def datadog(): return jsonify({"ok": True})
