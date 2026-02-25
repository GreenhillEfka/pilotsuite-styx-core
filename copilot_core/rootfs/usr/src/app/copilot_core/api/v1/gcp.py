from flask import Blueprint, jsonify
from copilot_core.api.security import require_token
gcp_bp = Blueprint("gcp", __name__, url_prefix="/api/v1/gcp")
@gcp_bp.route("", methods=["GET"])
@require_token
def gcp(): return jsonify({"ok": True})
