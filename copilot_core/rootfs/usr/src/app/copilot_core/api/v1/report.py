from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
report_bp = Blueprint("report", __name__, url_prefix="/api/v1/report")
@report_bp.route("", methods=["GET"])
@require_token
def report(): return jsonify({"ok": True})
