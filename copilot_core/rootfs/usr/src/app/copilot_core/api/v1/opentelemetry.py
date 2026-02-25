from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
opentelemetry_bp = Blueprint("opentelemetry", __name__, url_prefix="/api/v1/opentelemetry")
@opentelemetry_bp.route("", methods=["GET"])
@require_token
def opentelemetry(): return jsonify({"ok": True})
