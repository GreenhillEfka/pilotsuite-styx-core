from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
typesense_bp = Blueprint("typesense", __name__, url_prefix="/api/v1/typesense")
@typesense_bp.route("", methods=["GET"])
@require_token
def typesense(): return jsonify({"ok": True})
